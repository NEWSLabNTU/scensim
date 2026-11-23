"""How a scensim FileHeader property names a scenario parameter (issue 131).

A binding (`scensim.knob.<knob>`, a knob profile's breakpoints, `scensim.anchor.<parameter>`,
`scensim.pilot_map`) names a parameter as `param:<name>`:

    <Property name="scensim.knob.illumination" value="param:illumination"/>
    <Property name="scensim.knob.visibility" value="time: 0 1000; 12 param:fog_end"/>
    <Property name="scensim.anchor.exit_lane" value="exit_n.lanelet_at(param:cyclist_s)"/>
    <Property name="scensim.pilot_map" value="param:pm"/>

never as `$<name>`: OpenSCENARIO evaluates a FileHeader property before the scenario's
parameters are declared, so a `$` there fails in every OpenSCENARIO tool (SSv2's preprocessor:
`No such variable named "<name>"`). A `$` in any scensim.* FileHeader property is refused by
name, with the form to write. Internally the parameter is `$<name>` again (`internal`), so the
code that resolves bindings reads one form.
"""
import re

PARAM = "param:"
PREFIX = "scensim."
_TOKEN = re.compile(r"param:([A-Za-z_][A-Za-z0-9_]*)")
_DOLLAR = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")


class BindingError(ValueError):
    pass


def written(value: str) -> str:
    """``value`` as it should be written: each ``$<name>`` or ``${name}`` as ``param:<name>``."""
    return _DOLLAR.sub(r"param:\1", value or "")


def internal(name: str, value, where: str) -> str:
    """A scensim.* FileHeader property's ``value`` with each ``param:<name>`` as ``$<name>``;
    a ``$`` in it refused (BindingError), naming the property and the form to write."""
    v = value or ""
    if "$" in v:
        raise BindingError(
            f"{where}: FileHeader {name} = {v!r}: a scensim property names a parameter as "
            f"param:<name>, not $<name>, since OpenSCENARIO evaluates a FileHeader property "
            f"before the parameters exist (issue 131): write {written(v)!r}")
    return _TOKEN.sub(r"$\1", v)
