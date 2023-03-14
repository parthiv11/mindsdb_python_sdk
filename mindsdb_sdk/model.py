import pandas as pd

from mindsdb_sql.parser.dialects.mindsdb import *
from mindsdb_sql.parser.ast import *
from mindsdb_sql import parse_sql
from mindsdb_sql.planner.utils import query_traversal

from mindsdb_sdk.utils import dict_to_binary_op
from mindsdb_sdk.query import Query


class Model:
    def __init__(self, project, data):
        self.project = project

        self.data = data
        self.name = data['name']
        self.version = None

    def __repr__(self):
        version = ''
        if self.version is not None:
            version = f', version={self.version}'
        return f'{self.__class__.__name__}({self.name}{version}, status={self.data["status"]})'

    def _get_identifier(self):
        parts = [self.project.name, self.name]
        if self.version is not None:
            parts.append(str(self.version))
        return Identifier(parts=parts)

    def predict(self, data, params=None):
        if isinstance(data, Query):
            # create join from select if it is simple select
            ast_query = parse_sql(data.sql, dialect='mindsdb')
            if isinstance(ast_query, Select) and isinstance(ast_query.from_table, Identifier):
                # inject aliases
                if ast_query.from_table.alias is None:
                    alias = 't'
                    ast_query.from_table.alias = Identifier(alias)
                else:
                    alias = ast_query.from_table.alias.parts[-1]

                def inject_alias(node, is_table, **kwargs):
                    if not is_table:
                        if isinstance(node, Identifier):
                            if node.parts[0] != alias:
                                node.parts.insert(0, alias)

                query_traversal(ast_query, inject_alias)

                # replace table with join
                ast_query.from_table = Join(
                    join_type='join',
                    left=ast_query.from_table,
                    right=self._get_identifier()
                )
            else:
                # wrap query to subselect
                ast_query.parentheses = True
                ast_query = Select(
                    targets=[Star()],
                    from_table=Join(
                        join_type='join',
                        left=ast_query,
                        right=self._get_identifier()
                    )
                )
            if params is not None:
                ast_query.using = params
            # execute in query's database
            return self.project.api.sql_query(ast_query.to_string(), database=data.database)

        elif isinstance(data, pd.DataFrame):
            return self.project.api.model_predict(self.project.name, self.name, data,
                                                  params=params, version=self.version)
        else:
            raise ValueError('Unknown input')

    def get_status(self):
        self.refresh()
        return self.data['status']

    def refresh(self):
        model = self.project.get_model(self.name, self.version)
        self.data = model.data

    def adjust(self, query=None, database=None, options=None, engine=None):
        return self._retrain(query=query, database=database,
                             options=options, engine=engine,
                             klass=AdjustPredictor)

    def retrain(self, query=None, database=None, options=None, engine=None):
        return self._retrain(query=query, database=database,
                             options=options, engine=engine,
                             klass=RetrainPredictor)

    def _retrain(self, query=None, database=None, options=None, engine=None, klass=None):
        if isinstance(query, Query):
            database = query.database
            query = query.sql
        elif isinstance(query, pd.DataFrame):
            raise NotImplementedError('Dataframe as input for training model is not supported yet')

        if database is not None:
            database = Identifier(database)

        if options is None:
            options = {}
        if engine is not None:
            options['engine'] = engine

        ast_query = klass(
            name=self._get_identifier(),
            query_str=query,
            integration_name=database,
            using=options or None,
        )

        data = self.project.query(ast_query.to_string()).fetch()
        data = {k.lower(): v for k, v in data.items()}

        # return new instance
        base_class = self.__class__
        return base_class(self.project, data)

    def describe(self, type=None):
        identifier = self._get_identifier()
        if type is not None:
            identifier.parts.append(type)
        ast_query = Describe(identifier)
        return self.project.query(ast_query.to_string()).fetch()

    def list_versions(self):
        return self.project.list_models(with_versions=True, name=self.name)

    def set_active(self, version):
        ast_query = Update(
            table=Identifier('models_versions'),
            update_columns={
                'active': Constant(1)
            },
            where=dict_to_binary_op({
                'name': self.name,
                'version': version
            })
        )
        self.project.query(ast_query.to_string()).fetch()
        self.refresh()


class ModelVersion(Model):
    def __init__(self, project, data):

        super().__init__(project, data)

        self.version = data['version']