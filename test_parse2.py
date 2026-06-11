import re
query = 'title:"Memory Warning"'
pattern = re.compile(
    r'(?:(?P<key>[a-zA-Z0-9_]+):)?'
    r'(?:'
    r'/(?P<regex>(?:\\/|[^/])+)/|'
    r'"(?P<dquote>(?:\\"|[^"])+)"|'
    r"'(?P<squote>(?:\\'|[^'])+)'|"
    r'(?P<unquoted>[^\s]+)'
    r')'
)
print("Matches:")
for match in pattern.finditer(query):
    print(match.groupdict())
