import narwhals as nw
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.utils.validation import check_is_fitted

from sklego.common import as_list


class ColumnDropper(BaseEstimator, TransformerMixin):
    """The `ColumnDropper` transformer allows dropping specific columns from a DataFrame by name.
    Can be useful in a sklearn Pipeline.

    Parameters
    ----------
    columns : str | list[str]
        Column name(s) to be selected.

    Attributes
    ----------
    feature_names_ : list[str]
        The names of the features to keep during transform.

    Notes
    -----
    Native cross-dataframe support is achieved using
    [Narwhals](https://narwhals-dev.github.io/narwhals/){:target="_blank"}.

    Supported dataframes are:

    - pandas
    - Polars (eager or lazy)
    - Modin
    - cuDF

    See [Narwhals docs](https://narwhals-dev.github.io/narwhals/extending/){:target="_blank"} for an up-to-date list
    (and to learn how you can add your dataframe library to it!).

    Examples
    --------
    ```py
    # Selecting a single column from a pandas DataFrame
    import pandas as pd
    from sklego.preprocessing import ColumnDropper

    df = pd.DataFrame({
        "name": ["Swen", "Victor", "Alex"],
        "length": [1.82, 1.85, 1.80],
        "shoesize": [42, 44, 45]
    })
    ColumnDropper(["name"]).fit_transform(df)
    '''
       length  shoesize
    0    1.82        42
    1    1.85        44
    2    1.80        45
    '''

    # Dropping multiple columns from a pandas DataFrame
    ColumnDropper(["length", "shoesize"]).fit_transform(df)
    '''
         name
    0    Swen
    1  Victor
    2    Alex
    '''

    # Dropping non-existent columns results in a KeyError
    ColumnDropper(["weight"]).fit_transform(df)
    # Traceback (most recent call last):
    #     ...
    # KeyError: "['weight'] column(s) not in DataFrame"

    # How to use the ColumnSelector in a sklearn Pipeline
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    pipe = Pipeline([
        ("select", ColumnDropper(["name", "shoesize"])),
        ("scale", StandardScaler()),
    ])
    pipe.fit_transform(df)
    # array([[-0.16222142],
    #        [ 1.29777137],
    #        [-1.13554995]])
    ```

    Raises
    ------
    TypeError
        If input provided is not a DataFrame.
    KeyError
        If columns provided are not in the input DataFrame.
    ValueError
        If dropping the specified columns would result in an empty output DataFrame.
    """

    def __init__(self, columns: list):
        self.columns = columns

    def fit(self, X, y=None):
        """Fit the transformer by storing the column names to keep during `.transform()` step.

        Checks:

        1. If input is a supported DataFrame
        2. If column names are in such DataFrame

        Parameters
        ----------
        X : DataFrame
            The data on which we apply the column selection.
        y : Series, default=None
            Ignored, present for compatibility.

        Returns
        -------
        self : ColumnDropper
            The fitted transformer.

        Raises
        ------
        TypeError
            If `X` is not a supported DataFrame.
        KeyError
            If one or more of the columns provided doesn't exist in the input DataFrame.
        ValueError
            If dropping the specified columns would result in an empty output DataFrame.
        """
        self.columns_ = as_list(self.columns)
        X = nw.from_native(X)
        self._check_column_names(X)
        self.feature_names_ = [x for x in X.columns if x not in self.columns_]
        self._check_column_length()
        return self

    def transform(self, X):
        """Returns a DataFrame with only the specified columns.

        Parameters
        ----------
        X : DataFrame
            The data on which we apply the column selection.

        Returns
        -------
        DataFrame
            The data with the specified columns dropped.

        Raises
        ------
        TypeError
            If `X` is not a supported DataFrame object.
        """
        check_is_fitted(self, ["feature_names_"])
        X = nw.from_native(X)
        if self.columns_:
            return nw.to_native(X.drop(self.columns_))
        return nw.to_native(X)

    def get_feature_names(self):
        """Alias for `.feature_names_` attribute"""
        return self.feature_names_

    def _check_column_length(self):
        """Check if all columns are dropped"""
        if len(self.feature_names_) == 0:
            raise ValueError(f"Dropping {self.columns_} would result in an empty output DataFrame")

    def _check_column_names(self, X):
        """Check if one or more of the columns provided doesn't exist in the input DataFrame"""
        non_existent_columns = set(self.columns_).difference(X.columns)
        if len(non_existent_columns) > 0:
            raise KeyError(f"{list(non_existent_columns)} column(s) not in DataFrame")


class PandasTypeSelector(BaseEstimator, TransformerMixin):
    """The `PandasTypeSelector` transformer allows to select columns in a pandas DataFrame based on their type.
    Can be useful in a sklearn Pipeline.

    It uses
    [pandas.DataFrame.select_dtypes](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.select_dtypes.html)
    method.

    Parameters
    ----------
    include : scalar or list-like
        Column type(s) to be selected
    exclude : scalar or list-like
        Column type(s) to be excluded from selection

    Attributes
    ----------
    feature_names_ : list[str]
        The names of the features to keep during transform.
    X_dtypes_ : pd.Series
        The dtypes of the columns in the input DataFrame.

    !!! warning

        Raises a `TypeError` if input provided is not a DataFrame.

    Examples
    --------
    ```py
    import pandas as pd
    from sklego.preprocessing import PandasTypeSelector

    df = pd.DataFrame({
        "name": ["Swen", "Victor", "Alex"],
        "length": [1.82, 1.85, 1.80],
        "shoesize": [42, 44, 45]
    })

    #Excluding single column
    PandasTypeSelector(exclude="int64").fit_transform(df)
    #	name	length
    #0	Swen	1.82
    #1	Victor	1.85
    #2	Alex	1.80

    #Including multiple columns
    PandasTypeSelector(include=["int64", "object"]).fit_transform(df)
    #	name	shoesize
    #0	Swen	42
    #1	Victor	44
    #2	Alex	45
    ```
    """

    def __init__(self, include=None, exclude=None):
        self.include = include
        self.exclude = exclude

    def fit(self, X, y=None):
        """Fit the transformer by saving the column names to keep during transform.

        Parameters
        ----------
        X : pd.DataFrame
            The data on which we apply the column selection.
        y : pd.Series, default=None
            Ignored, present for compatibility.

        Returns
        -------
        self : PandasTypeSelector
            The fitted transformer.

        Raises
        ------
        TypeError
            If `X` is not a `pd.DataFrame` object.
        ValueError
            If provided type(s) results in empty dataframe.
        """
        self._check_X_for_type(X)
        self.X_dtypes_ = X.dtypes
        self.feature_names_ = list(X.select_dtypes(include=self.include, exclude=self.exclude).columns)

        if len(self.feature_names_) == 0:
            raise ValueError("Provided type(s) results in empty dataframe")

        return self

    def get_feature_names(self, *args, **kwargs):
        """Alias for `.feature_names_` attribute"""
        return self.feature_names_

    def transform(self, X):
        """Returns a pandas DataFrame with columns (de)selected based on their dtype.

        Parameters
        ----------
        X : pd.DataFrame
            The data to select dtype for.

        Returns
        -------
        pd.DataFrame
            The data with the specified columns selected.

        Raises
        ------
        TypeError
            If `X` is not a `pd.DataFrame` object.
        ValueError
            If column dtypes were not equal during fit and transform.
        """
        check_is_fitted(self, ["X_dtypes_", "feature_names_"])

        try:
            if (self.X_dtypes_ != X.dtypes).any():
                raise ValueError(
                    f"Column dtypes were not equal during fit and transform. Fit types: \n"
                    f"{self.X_dtypes_}\n"
                    f"transform: \n"
                    f"{X.dtypes}"
                )
        except ValueError as e:
            raise ValueError("Columns were not equal during fit and transform") from e

        self._check_X_for_type(X)
        transformed_df = X.select_dtypes(include=self.include, exclude=self.exclude)

        return transformed_df

    @staticmethod
    def _check_X_for_type(X):
        """Checks if input of the Selector is of the required dtype"""
        if not isinstance(X, pd.DataFrame):
            raise TypeError("Provided variable X is not of type pandas.DataFrame")


class ColumnSelector(BaseEstimator, TransformerMixin):
    """The `ColumnSelector` transformer allows selecting specific columns from a DataFrame by name.
    Can be useful in a sklearn Pipeline.

    Parameters
    ----------
    columns : str | list[str]
        Column name(s) to be selected.

    Notes
    -----
    Native cross-dataframe support is achieved using
    [Narwhals](https://narwhals-dev.github.io/narwhals/){:target="_blank"}.

    Supported dataframes are:

    - pandas
    - Polars (eager or lazy)
    - Modin
    - cuDF

    See [Narwhals docs](https://narwhals-dev.github.io/narwhals/extending/){:target="_blank"} for an up-to-date list
    (and to learn how you can add your dataframe library to it!).

    Attributes
    ----------
    columns_ : list[str]
        The names of the features to keep during transform.

    Examples
    --------
    ```py
    # Selecting a single column from a pandas DataFrame
    import pandas as pd
    from sklego.preprocessing import ColumnSelector

    df_pd = pd.DataFrame({
        "name": ["Swen", "Victor", "Alex"],
        "length": [1.82, 1.85, 1.80],
        "shoesize": [42, 44, 45]
    })

    ColumnSelector(["length"]).fit_transform(df_pd)
    '''
        length
    0    1.82
    1    1.85
    2    1.80
    '''

    # Selecting multiple columns from a polars DataFrame
    import polars as pl
    from sklego.preprocessing import ColumnSelector

    df_pl = pl.DataFrame({
        "name": ["Swen", "Victor", "Alex"],
        "length": [1.82, 1.85, 1.80],
        "shoesize": [42, 44, 45]
    })

    ColumnSelector(["length", "shoesize"]).fit_transform(df_pl)
    '''
    shape: (3, 2)
    ┌────────┬──────────┐
    │ length ┆ shoesize │
    │ ---    ┆ ---      │
    │ f64    ┆ i64      │
    ╞════════╪══════════╡
    │ 1.82   ┆ 42       │
    │ 1.85   ┆ 44       │
    │ 1.8    ┆ 45       │
    └────────┴──────────┘
    '''


    # Selecting non-existent columns results in a KeyError
    ColumnSelector(["weight"]).fit_transform(df_pd)
    # Traceback (most recent call last):
    #     ...
    # KeyError: "['weight'] column(s) not in DataFrame"

    # How to use the ColumnSelector in a sklearn Pipeline
    import polars as pl
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklego.preprocessing import ColumnSelector

    pipe = Pipeline([
        ("select", ColumnSelector(["length"])),
        ("scale", StandardScaler()),
    ])
    pipe.fit_transform(df_pl)
    # array([[-0.16222142],
    #        [ 1.29777137],
    #        [-1.13554995]])
    ```

    Raises
    ------
    TypeError
        If input provided is not a supported DataFrame.
    KeyError
        If columns provided are not in the input DataFrame.
    ValueError
        If provided list of columns to select is empty and would result in an empty output DataFrame.
    """

    def __init__(self, columns: list):
        # if the columns parameter is not a list, make it into a list
        self.columns = columns

    def fit(self, X, y=None):
        """Fit the transformer by storing the column names to keep during transform.

        Checks:

        1. If input is a supported DataFrame
        2. If column names are in such DataFrame

        Parameters
        ----------
        X : DataFrame
            The data on which we apply the column selection.
        y : Series, default=None
            Ignored, present for compatibility.

        Returns
        -------
        self : ColumnSelector
            The fitted transformer.

        Raises
        ------
        TypeError
            If `X` is not a supported DataFrame
        KeyError
            If one or more of the columns provided doesn't exist in the input DataFrame.
        ValueError
            If provided list of columns to select is empty and would result in an empty output DataFrame.
        """
        self.columns_ = as_list(self.columns)
        X = nw.from_native(X)
        self._check_column_names(X)
        self._check_column_length()
        return self

    def transform(self, X):
        """Returns a DataFrame with only the specified columns.

        Parameters
        ----------
        X : DataFrame
            The data on which we apply the column selection.

        Returns
        -------
        DataFrame
            The data with the specified columns dropped.

        Raises
        ------
        TypeError
            If `X` is not a supported DataFrame.
        """
        X = nw.from_native(X)
        if self.columns:
            return nw.to_native(X.select(self.columns_))
        return nw.to_native(X)

    def get_feature_names(self):
        """Alias for `.columns_` attribute"""
        return self.columns_

    def _check_column_length(self):
        """Check if no column is selected"""
        if len(self.columns_) == 0:
            raise ValueError("Expected columns to be at least of length 1, found length of 0 instead")

    def _check_column_names(self, X):
        """Check if one or more of the columns provided doesn't exist in the input DataFrame"""
        non_existent_columns = set(self.columns_).difference(X.columns)
        if len(non_existent_columns) > 0:
            raise KeyError(f"{list(non_existent_columns)} column(s) not in DataFrame")
