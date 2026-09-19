"""Safe deterministic verification for bounded KHTN calculations.

The provider selects a whitelisted formula id and supplies typed values.  The
server independently recomputes the result. No expression, Python code, or
model-authored function is ever executed.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import math
import re
import unicodedata


@dataclass(frozen=True)
class NumericIssue:
    code: str
    message: str


@dataclass(frozen=True)
class UnitDef:
    dimension: str
    to_base: Decimal


def _unit_key(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or "").strip().lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn").replace("đ", "d")
    return text.replace(" ", "").replace("²", "2").replace("³", "3")


UNITS: dict[str, UnitDef] = {
    "1": UnitDef("dimensionless", Decimal("1")),
    "m": UnitDef("distance", Decimal("1")),
    "km": UnitDef("distance", Decimal("1000")),
    "cm": UnitDef("distance", Decimal("0.01")),
    "mm": UnitDef("distance", Decimal("0.001")),
    "s": UnitDef("time", Decimal("1")),
    "giay": UnitDef("time", Decimal("1")),
    "min": UnitDef("time", Decimal("60")),
    "phut": UnitDef("time", Decimal("60")),
    "h": UnitDef("time", Decimal("3600")),
    "gio": UnitDef("time", Decimal("3600")),
    "m/s": UnitDef("speed", Decimal("1")),
    "km/h": UnitDef("speed", Decimal("0.2777777777777777777777777778")),
    "%": UnitDef("percentage", Decimal("1")),
    "°c": UnitDef("temperature", Decimal("1")),
    "oc": UnitDef("temperature", Decimal("1")),
    "c": UnitDef("temperature", Decimal("1")),
    "nhip/phut": UnitDef("rate", Decimal("1")),
    "kg": UnitDef("mass", Decimal("1")),
    "g": UnitDef("mass", Decimal("0.001")),
    "m3": UnitDef("volume", Decimal("1")),
    "l": UnitDef("volume", Decimal("0.001")),
    "ml": UnitDef("volume", Decimal("0.000001")),
    "cm3": UnitDef("volume", Decimal("0.000001")),
    "kg/m3": UnitDef("density", Decimal("1")),
    "g/cm3": UnitDef("density", Decimal("1000")),
    "n": UnitDef("force", Decimal("1")),
    "m2": UnitDef("area", Decimal("1")),
    "cm2": UnitDef("area", Decimal("0.0001")),
    "pa": UnitDef("pressure", Decimal("1")),
    "n.m": UnitDef("moment", Decimal("1")),
    "nm": UnitDef("moment", Decimal("1")),
    "a": UnitDef("current", Decimal("1")),
    "ma": UnitDef("current", Decimal("0.001")),
    "v": UnitDef("voltage", Decimal("1")),
    "ω": UnitDef("resistance", Decimal("1")),
    "ohm": UnitDef("resistance", Decimal("1")),
    "mol": UnitDef("amount", Decimal("1")),
    "g/mol": UnitDef("molar_mass", Decimal("1")),
    "j": UnitDef("energy", Decimal("1")),
    "kj": UnitDef("energy", Decimal("1000")),
    "wh": UnitDef("energy", Decimal("3600")),
    "kwh": UnitDef("energy", Decimal("3600000")),
    "w": UnitDef("power", Decimal("1")),
    "kw": UnitDef("power", Decimal("1000")),
    "j/(kg.°c)": UnitDef("specific_heat", Decimal("1")),
    "j/kg°c": UnitDef("specific_heat", Decimal("1")),
    "m/s2": UnitDef("acceleration", Decimal("1")),
}


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("boolean is not a numeric value")
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid numeric value: {value}") from exc


def _convert(value: Decimal, source_unit: str, target_unit: str) -> Decimal:
    source = UNITS.get(_unit_key(source_unit))
    target = UNITS.get(_unit_key(target_unit))
    if source is None or target is None:
        raise ValueError(f"unsupported unit conversion: {source_unit} -> {target_unit}")
    if source.dimension != target.dimension:
        raise ValueError(f"incompatible units: {source_unit} and {target_unit}")
    return value * source.to_base / target.to_base


def _known(calculation: dict) -> dict[str, tuple[Decimal, str]]:
    result: dict[str, tuple[Decimal, str]] = {}
    aliases = {
        "distance": "s",
        "quang_duong": "s",
        "time": "t",
        "thoi_gian": "t",
        "speed": "v",
        "toc_do": "v",
        "initial": "initial",
        "final": "final",
        "start": "initial",
        "end": "final",
    }
    for item in calculation.get("known_values") or []:
        raw_symbol = _unit_key(item.get("symbol")).replace("-", "_")
        symbol = aliases.get(raw_symbol, raw_symbol)
        if symbol:
            result[symbol] = (_decimal(item.get("value")), str(item.get("unit") or ""))
    return result


def _solve_speed(calculation: dict) -> tuple[Decimal, str, str]:
    values = _known(calculation)
    target = _unit_key(calculation.get("target_symbol"))
    aliases = {"speed": "v", "toc_do": "v", "distance": "s", "quang_duong": "s", "time": "t", "thoi_gian": "t"}
    target = aliases.get(target, target)
    result_unit = str((calculation.get("result") or {}).get("unit") or "")

    if target == "v":
        distance = _convert(*values["s"], "m")
        duration = _convert(*values["t"], "s")
        if duration == 0:
            raise ValueError("time must be non-zero")
        value = _convert(distance / duration, "m/s", result_unit)
        return value, result_unit, "v = s / t"
    if target == "s":
        speed = _convert(*values["v"], "m/s")
        duration = _convert(*values["t"], "s")
        value = _convert(speed * duration, "m", result_unit)
        return value, result_unit, "s = v × t"
    if target == "t":
        distance = _convert(*values["s"], "m")
        speed = _convert(*values["v"], "m/s")
        if speed == 0:
            raise ValueError("speed must be non-zero")
        value = _convert(distance / speed, "s", result_unit)
        return value, result_unit, "t = s / v"
    raise ValueError(f"unsupported SPEED target: {target}")


def _solve_data(calculation: dict, *, percentage: bool) -> tuple[Decimal, str, str]:
    values = _known(calculation)
    initial, initial_unit = values["initial"]
    final, final_unit = values["final"]
    final = _convert(final, final_unit, initial_unit)
    if percentage:
        if initial == 0:
            raise ValueError("initial value must be non-zero for percentage change")
        return (final - initial) / initial * Decimal("100"), "%", "(final - initial) / initial × 100%"
    result_unit = str((calculation.get("result") or {}).get("unit") or initial_unit)
    return _convert(final - initial, initial_unit, result_unit), result_unit, "final - initial"


def _target(calculation: dict, aliases: dict[str, str] | None = None) -> str:
    value = _unit_key(calculation.get("target_symbol")).replace("-", "_")
    return (aliases or {}).get(value, value)


def _solve_mass_moles(calculation: dict) -> tuple[Decimal, str, str]:
    values = _known(calculation)
    target = _target(calculation, {"mass": "m", "amount": "n"})
    result_unit = str((calculation.get("result") or {}).get("unit") or "")
    if target == "m":
        amount = _convert(*values["n"], "mol")
        molar_mass = _convert(*values["molar_mass"], "g/mol")
        return _convert(amount * molar_mass, "g", result_unit), result_unit, "m = n × M"
    if target == "n":
        mass = _convert(*values["m"], "g")
        molar_mass = _convert(*values["molar_mass"], "g/mol")
        if molar_mass == 0:
            raise ValueError("molar mass must be non-zero")
        return _convert(mass / molar_mass, "mol", result_unit), result_unit, "n = m / M"
    if target == "molar_mass":
        mass = _convert(*values["m"], "g")
        amount = _convert(*values["n"], "mol")
        if amount == 0:
            raise ValueError("amount must be non-zero")
        return _convert(mass / amount, "g/mol", result_unit), result_unit, "M = m / n"
    raise ValueError(f"unsupported MASS_MOLES target: {target}")


def _solve_concentration(calculation: dict) -> tuple[Decimal, str, str]:
    values = _known(calculation)
    solute = values.get("m_solute") or values.get("solute")
    solution = values.get("m_solution") or values.get("solution")
    if solute is None or solution is None:
        raise ValueError("CONCENTRATION_PERCENT requires m_solute and m_solution")
    solute_value = _convert(*solute, "g")
    solution_value = _convert(*solution, "g")
    if solution_value == 0:
        raise ValueError("solution mass must be non-zero")
    return solute_value / solution_value * Decimal("100"), "%", "C% = m_solute / m_solution × 100%"


def _solve_three_variable(
    calculation: dict,
    *,
    symbols: tuple[str, str, str],
    base_units: tuple[str, str, str],
    relationships: tuple[str, str, str],
) -> tuple[Decimal, str, str]:
    """Solve a=b/c and its two elementary rearrangements."""
    values = _known(calculation)
    target = _target(calculation)
    a, b, c = symbols
    a_unit, b_unit, c_unit = base_units
    result_unit = str((calculation.get("result") or {}).get("unit") or "")
    if target == a:
        b_value = _convert(*values[b], b_unit)
        c_value = _convert(*values[c], c_unit)
        if c_value == 0:
            raise ValueError(f"{c} must be non-zero")
        return _convert(b_value / c_value, a_unit, result_unit), result_unit, relationships[0]
    if target == b:
        a_value = _convert(*values[a], a_unit)
        c_value = _convert(*values[c], c_unit)
        return _convert(a_value * c_value, b_unit, result_unit), result_unit, relationships[1]
    if target == c:
        b_value = _convert(*values[b], b_unit)
        a_value = _convert(*values[a], a_unit)
        if a_value == 0:
            raise ValueError(f"{a} must be non-zero")
        return _convert(b_value / a_value, c_unit, result_unit), result_unit, relationships[2]
    raise ValueError(f"unsupported target: {target}")


def _solve_product(calculation: dict, *, symbols, units, relationship) -> tuple[Decimal, str, str]:
    values = _known(calculation)
    target = _target(calculation)
    result_symbol, left_symbol, right_symbol = symbols
    result_base, left_base, right_base = units
    result_unit = str((calculation.get("result") or {}).get("unit") or "")
    if target == result_symbol:
        value = _convert(*values[left_symbol], left_base) * _convert(*values[right_symbol], right_base)
        return _convert(value, result_base, result_unit), result_unit, relationship
    if target == left_symbol:
        divisor = _convert(*values[right_symbol], right_base)
        if divisor == 0:
            raise ValueError(f"{right_symbol} must be non-zero")
        value = _convert(*values[result_symbol], result_base) / divisor
        return _convert(value, left_base, result_unit), result_unit, relationship
    if target == right_symbol:
        divisor = _convert(*values[left_symbol], left_base)
        if divisor == 0:
            raise ValueError(f"{left_symbol} must be non-zero")
        value = _convert(*values[result_symbol], result_base) / divisor
        return _convert(value, right_base, result_unit), result_unit, relationship
    raise ValueError(f"unsupported target: {target}")


def _solve_heat(calculation: dict) -> tuple[Decimal, str, str]:
    values = _known(calculation)
    mass = _convert(*values["m"], "kg")
    specific_heat = _convert(*values["c"], "J/(kg.°C)")
    delta = _convert(*values.get("delta_t", values.get("dt")), "°C")
    result_unit = str((calculation.get("result") or {}).get("unit") or "J")
    return _convert(mass * specific_heat * delta, "J", result_unit), result_unit, "Q = m × c × Δt"


def _solve_kinetic(calculation: dict) -> tuple[Decimal, str, str]:
    values = _known(calculation)
    mass = _convert(*values["m"], "kg")
    speed = _convert(*values["v"], "m/s")
    result_unit = str((calculation.get("result") or {}).get("unit") or "J")
    return _convert(Decimal("0.5") * mass * speed * speed, "J", result_unit), result_unit, "Wđ = 1/2 × m × v²"


def _solve_potential(calculation: dict) -> tuple[Decimal, str, str]:
    values = _known(calculation)
    mass = _convert(*values["m"], "kg")
    gravity = _convert(*values["g"], "m/s2")
    height = _convert(*values["h"], "m")
    result_unit = str((calculation.get("result") or {}).get("unit") or "J")
    return _convert(mass * gravity * height, "J", result_unit), result_unit, "Wt = m × g × h"


def _composition_sum(calculation: dict) -> Decimal:
    values = _known(calculation)
    indexes = sorted(
        match.group(1)
        for symbol in values
        if (match := re.fullmatch(r"ar_?(\d+)", symbol))
    )
    if not indexes:
        # Accept conventional chemistry labels such as Ar(S), n(S), while
        # still reducing them to the same bounded value pairs. No expression is
        # parsed or executed.
        elements = sorted(
            match.group(1)
            for symbol in values
            if (match := re.fullmatch(r"ar\(([^)]+)\)", symbol))
        )
        if not elements or len(elements) > 8:
            raise ValueError("RELATIVE_MOLECULAR_MASS requires 1-8 ar_i/count_i pairs")
        total = Decimal("0")
        for element in elements:
            atomic = values[f"ar({element})"]
            count = values.get(f"n({element})") or values.get(f"count({element})")
            if count is None:
                raise ValueError(f"missing atom count for {element}")
            atomic_value = _convert(atomic[0], atomic[1] or "1", "1")
            count_value = _convert(count[0], count[1] or "1", "1")
            if count_value <= 0 or count_value != count_value.to_integral_value():
                raise ValueError("atom count must be a positive integer")
            total += atomic_value * count_value
        return total
    if len(indexes) > 8:
        raise ValueError("RELATIVE_MOLECULAR_MASS requires 1-8 ar_i/count_i pairs")
    total = Decimal("0")
    for index in indexes:
        atomic = values.get(f"ar_{index}") or values.get(f"ar{index}")
        count = values.get(f"count_{index}") or values.get(f"count{index}")
        if atomic is None or count is None:
            raise ValueError(f"missing ar/count pair {index}")
        atomic_value = _convert(atomic[0], atomic[1] or "1", "1")
        count_value = _convert(count[0], count[1] or "1", "1")
        if count_value <= 0 or count_value != count_value.to_integral_value():
            raise ValueError("atom count must be a positive integer")
        total += atomic_value * count_value
    return total


def _solve_relative_molecular_mass(calculation: dict) -> tuple[Decimal, str, str]:
    total = _composition_sum(calculation)
    result_unit = str((calculation.get("result") or {}).get("unit") or "1")
    return _convert(total, "1", result_unit), result_unit, "Mr = Σ(Ar × số nguyên tử)"


def _solve_molar_mass_from_composition(calculation: dict) -> tuple[Decimal, str, str]:
    total = _composition_sum(calculation)
    result_unit = str((calculation.get("result") or {}).get("unit") or "g/mol")
    return _convert(total, "g/mol", result_unit), result_unit, "M = Σ(Ar × số nguyên tử)"


def _solve_molar_gas_volume_stp(calculation: dict) -> tuple[Decimal, str, str]:
    values = _known(calculation)
    target = _target(calculation, {"volume": "v", "amount": "n"})
    result_unit = str((calculation.get("result") or {}).get("unit") or "")
    molar_volume = Decimal("22.4")
    if target == "v":
        amount = _convert(*values["n"], "mol")
        return _convert(amount * molar_volume, "L", result_unit), result_unit, "V = n × 22,4 L"
    if target == "n":
        volume = _convert(*values["v"], "L")
        return _convert(volume / molar_volume, "mol", result_unit), result_unit, "n = V / 22,4 L"
    raise ValueError(f"unsupported MOLAR_GAS_VOLUME_STP target: {target}")


def _solve_gas_relative_density_h2(calculation: dict) -> tuple[Decimal, str, str]:
    values = _known(calculation)
    target = _target(calculation, {"relative_density": "d_h2", "d": "d_h2"})
    result_unit = str((calculation.get("result") or {}).get("unit") or "1")
    if target == "d_h2":
        molar_mass_entry = (
            values.get("molar_mass")
            or values.get("m(a)")
            or values.get("ma")
        )
        if molar_mass_entry is None:
            raise ValueError("GAS_RELATIVE_DENSITY_H2 requires molar_mass")
        molar_mass = _convert(*molar_mass_entry, "g/mol")
        return _convert(molar_mass / Decimal("2"), "1", result_unit), result_unit, "d(A/H₂) = M(A) / 2"
    if target == "molar_mass":
        relative_density = _convert(*values["d_h2"], "1")
        return _convert(relative_density * Decimal("2"), "g/mol", result_unit), result_unit, "M(A) = 2 × d(A/H₂)"
    raise ValueError(f"unsupported GAS_RELATIVE_DENSITY_H2 target: {target}")


def _solve_mechanical_energy(calculation: dict) -> tuple[Decimal, str, str]:
    values = _known(calculation)
    target = _target(calculation, {"w": "mechanical_energy", "wd": "kinetic_energy", "wt": "potential_energy"})
    result_unit = str((calculation.get("result") or {}).get("unit") or "J")
    symbols = {
        "mechanical_energy": "mechanical_energy",
        "kinetic_energy": "kinetic_energy",
        "potential_energy": "potential_energy",
    }
    if target == "mechanical_energy":
        kinetic = _convert(*values[symbols["kinetic_energy"]], "J")
        potential = _convert(*values[symbols["potential_energy"]], "J")
        return _convert(kinetic + potential, "J", result_unit), result_unit, "W = Wđ + Wt"
    total = _convert(*values[symbols["mechanical_energy"]], "J")
    other = "potential_energy" if target == "kinetic_energy" else "kinetic_energy"
    if target not in {"kinetic_energy", "potential_energy"}:
        raise ValueError(f"unsupported MECHANICAL_ENERGY target: {target}")
    value = total - _convert(*values[symbols[other]], "J")
    return _convert(value, "J", result_unit), result_unit, "W thành phần = W − W còn lại"


def _resistance_values(calculation: dict) -> list[Decimal]:
    values = _known(calculation)
    resistances = [
        _convert(value, unit, "ohm")
        for symbol, (value, unit) in values.items()
        if re.fullmatch(r"r_?\d+", symbol)
    ]
    if len(resistances) < 2:
        raise ValueError("at least two resistor values are required")
    if any(value <= 0 for value in resistances):
        raise ValueError("resistance values must be positive")
    return resistances


def _solve_series_resistance(calculation: dict) -> tuple[Decimal, str, str]:
    if _target(calculation) != "r":
        raise ValueError("SERIES_RESISTANCE supports target r only")
    resistances = _resistance_values(calculation)
    result_unit = str((calculation.get("result") or {}).get("unit") or "ohm")
    return _convert(sum(resistances, Decimal("0")), "ohm", result_unit), result_unit, "R = R₁ + R₂ + …"


def _solve_parallel_resistance_two(calculation: dict) -> tuple[Decimal, str, str]:
    if _target(calculation) != "r":
        raise ValueError("PARALLEL_RESISTANCE_TWO supports target r only")
    resistances = _resistance_values(calculation)
    if len(resistances) != 2:
        raise ValueError("PARALLEL_RESISTANCE_TWO requires exactly two resistors")
    left, right = resistances
    result_unit = str((calculation.get("result") or {}).get("unit") or "ohm")
    equivalent = left * right / (left + right)
    return _convert(equivalent, "ohm", result_unit), result_unit, "R = R₁R₂ / (R₁ + R₂)"


SOLVERS = {
    "RELATIVE_MOLECULAR_MASS": _solve_relative_molecular_mass,
    "SPEED": _solve_speed,
    "MASS_MOLES": _solve_mass_moles,
    "MOLAR_MASS_FROM_COMPOSITION": _solve_molar_mass_from_composition,
    "MOLAR_GAS_VOLUME_STP": _solve_molar_gas_volume_stp,
    "GAS_RELATIVE_DENSITY_H2": _solve_gas_relative_density_h2,
    "CONCENTRATION_PERCENT": _solve_concentration,
    "DENSITY": lambda calculation: _solve_three_variable(
        calculation,
        symbols=("d", "m", "v"),
        base_units=("kg/m3", "kg", "m3"),
        relationships=("D = m / V", "m = D × V", "V = m / D"),
    ),
    "PRESSURE": lambda calculation: _solve_three_variable(
        calculation,
        symbols=("p", "f", "s"),
        base_units=("Pa", "N", "m2"),
        relationships=("p = F / S", "F = p × S", "S = F / p"),
    ),
    "MOMENT": lambda calculation: _solve_product(
        calculation,
        symbols=("m", "f", "d"),
        units=("N.m", "N", "m"),
        relationship="M = F × d",
    ),
    "OHM": lambda calculation: _solve_product(
        calculation,
        symbols=("u", "i", "r"),
        units=("V", "A", "ohm"),
        relationship="U = I × R",
    ),
    "HEAT": _solve_heat,
    "KINETIC_ENERGY": _solve_kinetic,
    "POTENTIAL_ENERGY": _solve_potential,
    "MECHANICAL_ENERGY": _solve_mechanical_energy,
    "ELECTRIC_POWER": lambda calculation: _solve_product(
        calculation,
        symbols=("p", "u", "i"),
        units=("W", "V", "A"),
        relationship="P = U × I",
    ),
    "ELECTRIC_ENERGY": lambda calculation: _solve_product(
        calculation,
        symbols=("e", "p", "t"),
        units=("J", "W", "s"),
        relationship="E = P × t",
    ),
    "SERIES_RESISTANCE": _solve_series_resistance,
    "PARALLEL_RESISTANCE_TWO": _solve_parallel_resistance_two,
    "DATA_DIFFERENCE": lambda calculation: _solve_data(calculation, percentage=False),
    "PERCENT_CHANGE": lambda calculation: _solve_data(calculation, percentage=True),
}


def solve_calculation(calculation: dict) -> tuple[Decimal, str, str]:
    formula_id = str(calculation.get("formula_id") or "").upper()
    solver = SOLVERS.get(formula_id)
    if solver is None:
        raise ValueError(f"unsupported formula id: {formula_id}")
    return solver(calculation)


NUMBER_WITH_UNIT = re.compile(
    r"(?<![\w])(-?\d+(?:[.,]\d+)?)\s*(kg/m(?:3|³)|g/cm(?:3|³)|g/mol|j/\(kg\.°c\)|n\.m|km/h|m/s(?:2|²)?|cm(?:2|²|3|³)|m(?:2|²|3|³)|kwh|wh|kw|w|km|cm|mm|kg|g|mol|l|ml|pa|ohm|ω|a|v|j|kj|n|giờ|gio|h|phút|phut|min|giây|giay|s|%|°c|nhịp/phút|nhip/phut)(?=\s|$|[).,;])",
    flags=re.IGNORECASE,
)


def _option_value(text: object, *, target_unit: str) -> Decimal | None:
    if _unit_key(target_unit) == "1":
        dimensionless = re.search(r"(?<![\w])(-?\d+(?:[.,]\d+)?)(?![\w/%])", str(text or ""))
        if dimensionless:
            return _decimal(dimensionless.group(1))
    match = NUMBER_WITH_UNIT.search(str(text or ""))
    if not match:
        return None
    value = _decimal(match.group(1))
    unit = match.group(2)
    try:
        return _convert(value, unit, target_unit)
    except ValueError:
        return None


def _close(left: Decimal, right: Decimal, decimals: int | None) -> bool:
    if decimals is not None:
        quantum = Decimal(1).scaleb(-decimals)
        return left.quantize(quantum) == right.quantize(quantum)
    tolerance = max(Decimal("0.000001"), abs(right) * Decimal("0.000001"))
    return abs(left - right) <= tolerance


def validate_calculation(calculation: dict | None, question: dict, answer: dict) -> list[NumericIssue]:
    if not isinstance(calculation, dict):
        return [NumericIssue("numeric_spec_missing", "Câu định lượng thiếu đặc tả tính toán để kiểm chứng độc lập.")]
    issues: list[NumericIssue] = []
    try:
        expected, expected_unit, _relationship = solve_calculation(calculation)
    except (KeyError, ValueError, ArithmeticError) as exc:
        return [NumericIssue("numeric_solver_error", f"Không thể giải đặc tả số học an toàn: {exc}")]

    proposed = calculation.get("result") or {}
    try:
        proposed_value = _convert(
            _decimal(proposed.get("value")),
            str(proposed.get("unit") or expected_unit),
            expected_unit,
        )
    except ValueError as exc:
        issues.append(NumericIssue("numeric_result_invalid", str(exc)))
        proposed_value = None
    decimals = calculation.get("rounding_decimals")
    if decimals is not None and (not isinstance(decimals, int) or not 0 <= decimals <= 6):
        issues.append(NumericIssue("rounding_invalid", "Số chữ số làm tròn phải nằm trong khoảng 0-6."))
        decimals = None
    if proposed_value is not None and not _close(proposed_value, expected, decimals):
        issues.append(
            NumericIssue(
                "numeric_result_mismatch",
                f"Kết quả đề xuất {proposed_value} {expected_unit} không khớp kết quả máy chủ {expected} {expected_unit}.",
            )
        )

    if question.get("type") == "multiple_choice":
        correct_label = str(answer.get("correct_answer") or question.get("correct_answer") or "").upper()
        equivalent_labels = []
        for label, option in (question.get("options") or {}).items():
            option_value = _option_value(option, target_unit=expected_unit)
            if option_value is not None and _close(option_value, expected, decimals):
                equivalent_labels.append(str(label).upper())
        if correct_label not in equivalent_labels:
            issues.append(NumericIssue("correct_option_numeric_mismatch", "Phương án được đánh dấu đúng không chứa kết quả số học đã kiểm chứng."))
        if len(equivalent_labels) != 1:
            issues.append(
                NumericIssue(
                    "numeric_correct_option_count",
                    f"Câu một lựa chọn có {len(equivalent_labels)} phương án tương đương kết quả đúng: {equivalent_labels}.",
                )
            )

    if any(not math.isfinite(float(value)) for value in (expected,)):
        issues.append(NumericIssue("numeric_non_finite", "Kết quả số học không hữu hạn."))
    if str(calculation.get("formula_id") or "").upper() == "SPEED":
        try:
            speed_mps = _convert(expected, expected_unit, "m/s")
        except ValueError:
            speed_mps = None
        context = unicodedata.normalize("NFD", str(question.get("content") or "").lower())
        context = "".join(char for char in context if unicodedata.category(char) != "Mn").replace("đ", "d")
        if speed_mps is not None and (
            ("di bo" in context and speed_mps > Decimal("15"))
            or ("xe dap" in context and speed_mps > Decimal("40"))
        ):
            issues.append(
                NumericIssue(
                    "scientific_sanity_speed",
                    "Kết quả tốc độ không hợp lý với đối tượng thực tế được mô tả.",
                )
            )
    return issues
