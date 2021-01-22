from sqlalchemy.engine.default import DefaultDialect
from sqlalchemy.sql.sqltypes import DateTime, NullType, String

text = str
int_type = int
str_type = str


class StringLiteral(String):
    """Teach SA how to literalize various things."""

    def literal_processor(self, dialect):
        super_processor = super(StringLiteral, self).literal_processor(dialect)

        def process(value):
            if isinstance(value, int_type):
                return text(value)
            if not isinstance(value, str_type):
                value = text(value)
            result = super_processor(value)
            return result

        return process


class LiteralDialect(DefaultDialect):
    colspecs = {
        # prevent various encoding explosions
        String: StringLiteral,
        # teach SA about how to literalize a datetime
        DateTime: StringLiteral,
        # don't format py2 long integers to NULL
        NullType: StringLiteral,
    }


def literalquery(statement):
    """NOTE: This is entirely insecure. DO NOT execute the resulting strings."""
    import sqlalchemy.orm

    if isinstance(statement, sqlalchemy.orm.Query):
        statement = statement.statement
    return statement.compile(
        dialect=LiteralDialect(),
        compile_kwargs={"literal_binds": True},
    ).string
