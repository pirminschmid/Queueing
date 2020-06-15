"""
Data store module
- mainly documentation of the functionality of the data store

  see main documentation for details about data analysis

  version 2018-12-03

  Copyright (c) 2018 Pirmin Schmid, MIT license.
"""

from database.datastore import data_store

data_store.put('a_1_b_1_c_1', 1)
data_store.put('a_1_b_1_c_2', 2)
data_store.put('a_1_b_2_c_3', 3)
data_store.put('a_1_b_1_c_4', 4)

print([x.value for x in data_store.filter_by_id_str('a_1_b_1')])
print([x.meta for x in data_store.filter_by_id_str('a_1_b_2')])
print([x.meta for x in data_store.filter_by_meta({'b': 1, 'c': '4'})])

data_store.config_meta_data_type_map('a_i_b_f_c_s')

print([x.value for x in data_store.filter_by_id_str('a_1_b_1')])
print([x.meta for x in data_store.filter_by_id_str('a_1_b_2')])
print([x.meta for x in data_store.filter_by_meta({'b': 1, 'c': '4'})])

