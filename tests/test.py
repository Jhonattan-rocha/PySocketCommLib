import re

regex_find_var_parameters = re.compile(r"/{(?P<type>\w+): (?P<name>\w+)}")

print(regex_find_var_parameters.findall("/user/"))