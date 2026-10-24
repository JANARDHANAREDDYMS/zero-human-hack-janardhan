import copy,json,unittest
from pathlib import Path
from customer_generation.currency import currency_code,simulation_currency_check
from customer_generation.compact import construct_specification
ROOT=Path(__file__).resolve().parents[2]
class CurrencyTests(unittest.TestCase):
 def test_reject_prose_before_simulation(self):
  for bad in ['USD (assumed)','usd','',None]:
   with self.assertRaises(ValueError):currency_code(bad)
  with self.assertRaises(ValueError):simulation_currency_check([{'budget':{'currency':'USD (assumed)'}}])
