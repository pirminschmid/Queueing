
from toolbox_to_external_use.toolbox import TableReader

t = TableReader('toolbox_test.txt', 'a', ['//'])
row = 0
while not t.complete():
    row += 1
    print(row, t.get_value('a', int), t.get_value('c', float), t.get_value('d'))
    t.next_line()
