import pytest
from taxnetlab.models.base import SpecificationNotValidatedError
from taxnetlab.models.optimal_tax_routing import run as tax
from taxnetlab.models.conduits_sinks import run as conduits
from taxnetlab.models.scalable_tda import run as tda

@pytest.mark.parametrize("runner", [tax, conduits, tda])
def test_unvalidated_methods_fail_explicitly(runner):
    with pytest.raises(SpecificationNotValidatedError):
        runner()
