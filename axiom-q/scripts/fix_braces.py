#!/usr/bin/env python3
"""One-shot brace fixer for TelemetryPanel.jsx"""

import sys

PATH = 'src/components/TelemetryPanel/TelemetryPanel.jsx'

with open(PATH, 'r', encoding='utf-8') as f:
    s = f.read()

# Build OLD/NEW strings by concatenation so the model can't accidentally
# collapse them to the same sequence.
o1 = '<' + 'span className="text-neon-cyan">' + '{' + 'n' + chr(60) + '/span>'
n1 = '<' + 'span className="text-neon-cyan">' + '{' + 'n' + '}' + chr(60) + '/span>'
o2 = '{' + 'stateLabelRef.current' + chr(60) + '/span>'
n2 = '{' + 'stateLabelRef.current' + '}' + chr(60) + '/span>'

print('OLD1:', repr(o1))
print('NEW1:', repr(n1))
print('OLD2:', repr(o2))
print('NEW2:', repr(n2))
print('OLD1 != NEW1:', o1 != n1)
print('OLD2 != NEW2:', o2 != n2)

c1 = s.count(o1)
c2 = s.count(o2)
print('OLD1 count:', c1, 'OLD2 count:', c2)

s = s.replace(o1, n1).replace(o2, n2)
print('NEW1 count after:', s.count(n1))
print('NEW2 count after:', s.count(n2))

with open(PATH, 'w', encoding='utf-8') as f:
    f.write(s)
print('Written.')
