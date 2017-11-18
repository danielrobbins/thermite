# Thermite
## An improved Thinkpad thermal management tool.

Thermite is a lightweight, highly responsive application written in python to control thermal management for systems that use the thinkpad_acpi module.

### requirements
- thinkpad_acpi module 
- config_intel_pstate option in the kernel
- intel_thermalclamp compiled for the kernel

Remember: the thinkpad_acpi module does not permit fan control 
unless explicitly directed to do so with the fan_control=1 option


