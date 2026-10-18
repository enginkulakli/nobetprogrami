# routers package
# Apply scheduler preference wrappers before any router imports scheduler functions.
from preference_rules import install_preference_rules
install_preference_rules()
