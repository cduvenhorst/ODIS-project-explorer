from object_loaders import MCD_DB_PARAMETER


# Strange naming, MCD_DB_PARAMETER is actually loaded instead
def load(stream):
    return MCD_DB_PARAMETER.load(stream)

