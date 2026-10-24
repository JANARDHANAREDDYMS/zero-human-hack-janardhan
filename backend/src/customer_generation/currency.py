"""Currency fields contain codes; explanations belong in provenance notes."""
import re

def currency_code(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Z]{3}',value):
        raise ValueError('Currency must be a three-letter uppercase code, such as USD; keep explanations in notes')
    return value

def simulation_currency_check(customers):
    for customer in customers:
        currency_code(customer['budget']['currency'])
        for requirement in customer.get('requirements',[]):
            if requirement.get('attribute')=='price' and requirement.get('unit') is not None:
                currency_code(requirement['unit'])
