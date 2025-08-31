import requests
import json
from datetime import datetime
date_str = datetime.now().strftime('%Y-%m-%d')
url = f'http://localhost:8000/api/dev/schedule?date_str={date_str}&range=day'
print('Calling:', url)
resp = requests.get(url)
print('Status:', resp.status_code)
if resp.status_code == 200:
    data = resp.json()
    print('Days:', data.get('days', []))
    hospitals = data.get('hospitals', [])
    print('Hospitals count:', len(hospitals))
    for h in hospitals:
        print(f'Hospital: {h[\"name\"]}')
        for dep in h.get('departments', []):
            print(f'  Dept: {dep[\"name\"]}')
            for doc in dep.get('doctors', []):
                windows = doc.get('windows', [])
                busy = doc.get('busy', [])
                print(f'    Doctor: {doc[\"name\"]} - Windows: {len(windows)}, Busy: {len(busy)}')
                if windows:
                    for w in windows[:2]:  # show first 2
                        print(f'      Window: {w[\"start\"]} to {w[\"end\"]} ({w[\"kind\"]})')
                if busy:
                    for b in busy[:2]:
                        print(f'      Busy: {b[\"start\"]} to {b[\"end\"]}')
else:
    print('Error:', resp.text)
"