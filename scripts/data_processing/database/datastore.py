"""
Data store module
- simple key-value store to organize data collection and lookup / filtering based on meta data.
- the encoding of the meta data follows the encoding of the rest of my Advanced Systems Lab (ASL)
  project data processing; project description follows on my homepage
  id_str consists of: key1_value1_key2_value2_key3_value3 (...)
- the lookup/filter mechanism follows the filter option implemented in my Barrelfish OlympOS
  name service Gaia (Advanced Operating System, AOS, 2017) using a fresh implementation
  of a serializable key-value store that allows iteration of lambda functions
  https://www.pirmin-schmid.ch/software/barrelfish-olympos/
- optionally, type casts can be defined for meta data (int, float, str)
- a singleton is offered as data_store module variable

  This store is *not* designed for performance: O(n) for all lookup/filter operations
  however, O(1) for inserts

  limitations: no error handling; not designed for multi-threaded access

  see main documentation for details about data analysis

  version 2018-12-03

  Copyright (c) 2018 Pirmin Schmid, MIT license.
"""


class Item:
    def __init__(self, id_str, meta, value):
        self.id = id_str
        self.meta = meta
        self.value = value


class DataStore:
    def __init__(self):
        self.store = {}
        self.type_map = {}

    # public API
    def put(self, id_str, value):
        """
        adds value with key id_str to the store
        :param id_str: key_value encoded meta data
        :param value:
        """
        self.store[id_str] = Item(id_str, self.meta_data_from_id_str(id_str), value)

    def get(self, id_str):
        """
        returns exact match; None if not found
        :param id_str:
        :return: Item object that contains id_str, meta, and the value
        """
        if id_str not in self.store:
            return None
        return self.store[id_str]

    def meta_data_from_id_str(self, id_str):
        """
        returns dictionary with meta data including type casting, if defined.
        :param id_str: encoded id string
        :return: meta data dict
        """
        tokens = id_str.split('_')
        result = {}
        for i in range(0, len(tokens), 2):
            result[tokens[i]] = tokens[i + 1]
        return self.apply_type_casts(result)

    def filter_by_meta(self, meta_data_dict):
        """
        returns all items of the store that match all elements of the meta_data_dict
        :param meta_data_dict:
        :return: list of Item objects
        """
        return self.filter_by_meta_helper(self.apply_type_casts(meta_data_dict))

    def filter_by_id_str(self, id_str):
        """
        returns all items of the store that match all elements of the id_str
        :param id_str:
        :return: list of Item objects
        """
        return self.filter_by_meta_helper(self.meta_data_from_id_str(id_str))

    def config_meta_data_type_map(self, config_str):
        """
        as an option, type casts can be applied to defined meta data keys
        use i (for int), f (for float), s (for string) as 'value' in the config_str
        default is string, if not defined
        note: for consistency with the cached meta data, all meta data dicts are recalculated in this call
        :param config_str: key-'value' encoding string with codes as defined; empty string to remove all cast info
        """
        tokens = config_str.split('_')
        self.type_map = {}
        for i in range(0, len(tokens), 2):
            t = tokens[i + 1]
            if t == 'i':
                self.type_map[tokens[i]] = int
            elif t == 'f':
                self.type_map[tokens[i]] = float
        # update cache
        for e in self.store.values():
            e.meta = self.apply_type_casts(e.meta)

    # internal helpers
    def apply_type_casts(self, meta_data_dict):
        result = {}
        for (k, v) in meta_data_dict.items():
            if k in self.type_map:
                result[k] = self.type_map[k](v)
            else:
                result[k] = str(v)
        return result

    def filter_by_meta_helper(self, formatted_meta_data_dict):
        result = []
        for e in self.store.values():
            meta = e.meta
            match = True
            for (k, v) in formatted_meta_data_dict.items():
                if k not in meta:
                    match = False
                    break
                if meta[k] != v:
                    match = False
                    break
            if match:
                result.append(e)
        return result


# optional singleton
data_store = DataStore()
