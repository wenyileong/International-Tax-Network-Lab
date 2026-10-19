from taxnetlab.models.base import SpecificationNotValidatedError
MODEL_ID = "scalable_tda"
MODEL_VERSION = "0.1.0-interface"
def run(*args, **kwargs):
    raise SpecificationNotValidatedError("Not implemented: specify the baseline Mapper and patent-specific pipeline separately before claiming reproduction.")
