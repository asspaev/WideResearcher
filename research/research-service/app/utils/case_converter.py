"""
Taken from
https://github.com/mahenzon/ri-sdk-python-wrapper/blob/master/ri_sdk_codegen/utils/case_converter.py
"""


def camel_case_to_snake_case(input_str: str) -> str:
    """
    >>> camel_case_to_snake_case("SomeSDK")
    'some_sdks'
    >>> camel_case_to_snake_case("RServoDrive")
    'r_servo_drives'
    >>> camel_case_to_snake_case("SDKDemo")
    'sdk_demos'
    """
    chars = []
    for c_idx, char in enumerate(input_str):
        if c_idx and char.isupper():
            nxt_idx = c_idx + 1
            flag = nxt_idx >= len(input_str) or input_str[nxt_idx].isupper()
            prev_char = input_str[c_idx - 1]
            if prev_char.isupper() and flag:
                pass
            else:
                chars.append("_")
        chars.append(char.lower())

    snake_case = "".join(chars)

    if snake_case.endswith(("s", "x", "z", "ch", "sh")):
        snake_case += "es"
    else:
        snake_case += "s"

    return snake_case
