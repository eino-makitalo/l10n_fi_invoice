#--*-- coding: utf-8 --*--

def calc_checksum(refnum_without_checksum):
    """return right checksum of refnum """
    kertoimet = (7, 3, 1)
    refnum_without_checksum = refnum_without_checksum.replace(' ', '')
    numbers_inverse_order = map(int, refnum_without_checksum[::-1])
    resultsum = sum(kertoimet[i % 3] * x for i, x in enumerate(numbers_inverse_order))
    return (10 - (resultsum % 10)) % 10
