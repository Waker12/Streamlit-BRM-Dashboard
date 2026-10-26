"""User-approved reporting policy, recorded 2026-10-25."""
EUR_TO_MYR = 4.64
FX_POLICY = 'Bosch fixed · EUR 1 = MYR 4.64'

def fixed_rate(source,target):
    if source==target:return 1.0
    if (source,target)==('EUR','MYR'):return EUR_TO_MYR
    if (source,target)==('MYR','EUR'):return 1/EUR_TO_MYR
    return None
