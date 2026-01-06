def grade_from_altitude(altitude_end: int) -> str:
    if altitude_end >= 90:
        return "A"
    if altitude_end >= 80:
        return "B"
    if altitude_end >= 65:
        return "C"
    return "D"
