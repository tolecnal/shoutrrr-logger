"""Restricted string formatting for admin/user-supplied alert email templates."""

import string


class RestrictedFormatter(string.Formatter):
    """A ``string.Formatter`` that only allows simple ``{name}`` substitutions.

    Rejects replacement fields that use attribute access (``{title.__class__}``)
    or indexing (``{message[0]}``), which ``str.format`` would otherwise resolve
    via ``getattr``/``__getitem__`` on the supplied objects.
    """

    def get_field(self, field_name, args, kwargs):
        if "." in field_name or "[" in field_name:
            raise ValueError(
                f"Attribute/index access is not allowed in template fields: {field_name!r}"
            )
        return super().get_field(field_name, args, kwargs)


def safe_format(template: str, /, **kwargs: object) -> str:
    """Format ``template`` allowing only simple ``{name}`` substitutions.

    Raises ``ValueError``/``KeyError``/``IndexError`` if the template is
    malformed, references an undefined field, or attempts attribute/index
    access on a field.
    """
    return RestrictedFormatter().vformat(template, (), kwargs)
