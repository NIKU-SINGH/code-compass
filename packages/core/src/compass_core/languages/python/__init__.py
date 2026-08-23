from compass_core.languages import registry
from compass_core.languages.python.extractor import PythonExtractor
from compass_core.languages.python.import_resolver import PythonImportResolver

registry.register_extractor(PythonExtractor())
registry.register_import_resolver(PythonImportResolver())
