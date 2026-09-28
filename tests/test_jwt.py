import sys, os
sys.path.insert(0, os.path.abspath('.'))

from datetime import timedelta
from app.utils.security import (
    create_access_token,
    decode_access_token,
    InvalidTokenError,
    TokenData,
)

SEP = '-' * 55
passed = 0
failed = 0

print(SEP)
print('  JWT Access Token Test')
print(SEP)

# Test 1: token is created and is a non-empty string
print('\n[1] create_access_token() returns a non-empty string')
token = create_access_token(user_id=42, role='hr')
if isinstance(token, str) and len(token) > 20:
    print('    PASS - token created, length=' + str(len(token)))
    passed += 1
else:
    print('    FAIL - token is missing or too short')
    failed += 1

# Test 2: token decodes without error
print('\n[2] decode_access_token() succeeds for a valid token')
try:
    data = decode_access_token(token)
    print('    PASS - decoded OK')
    passed += 1
except InvalidTokenError as e:
    print('    FAIL - raised InvalidTokenError: ' + str(e))
    failed += 1

# Test 3: user_id is correct
print('\n[3] Decoded user_id matches input')
data = decode_access_token(token)
if data.user_id == 42:
    print('    PASS - user_id=' + str(data.user_id))
    passed += 1
else:
    print('    FAIL - user_id expected 42, got ' + str(data.user_id))
    failed += 1

# Test 4: role is correct
print('\n[4] Decoded role matches input')
if data.role == 'hr':
    print('    PASS - role=' + data.role)
    passed += 1
else:
    print('    FAIL - role expected hr, got ' + data.role)
    failed += 1

# Test 5: expires_at is in the future
print('\n[5] expires_at is in the future')
from datetime import datetime, timezone
if data.expires_at > datetime.now(tz=timezone.utc):
    print('    PASS - expires_at=' + str(data.expires_at))
    passed += 1
else:
    print('    FAIL - token is already expired at creation')
    failed += 1

# Test 6: a tampered token is rejected
print('\n[6] Tampered token is rejected')
tampered = token[:-4] + 'XXXX'
try:
    decode_access_token(tampered)
    print('    FAIL - tampered token was accepted (CRITICAL)')
    failed += 1
except InvalidTokenError as e:
    print('    PASS - rejected: ' + str(e))
    passed += 1

# Test 7: an expired token is rejected
print('\n[7] Expired token is rejected')
expired_token = create_access_token(user_id=1, role='employee', expires_delta=timedelta(seconds=-1))
try:
    decode_access_token(expired_token)
    print('    FAIL - expired token was accepted (CRITICAL)')
    failed += 1
except InvalidTokenError as e:
    print('    PASS - rejected: ' + str(e))
    passed += 1

# Test 8: empty string is rejected
print('\n[8] Empty string is rejected')
try:
    decode_access_token('')
    print('    FAIL - empty token was accepted')
    failed += 1
except InvalidTokenError as e:
    print('    PASS - rejected: ' + str(e))
    passed += 1

# Test 9: completely random garbage is rejected
print('\n[9] Random garbage string is rejected')
try:
    decode_access_token('not.a.jwt')
    print('    FAIL - garbage token was accepted')
    failed += 1
except InvalidTokenError as e:
    print('    PASS - rejected: ' + str(e))
    passed += 1

# Test 10: TokenData is the correct type
print('\n[10] decode_access_token() returns a TokenData instance')
token2 = create_access_token(user_id=7, role='admin')
result = decode_access_token(token2)
if isinstance(result, TokenData) and result.user_id == 7 and result.role == 'admin':
    print('    PASS - TokenData(user_id=7, role=admin)')
    passed += 1
else:
    print('    FAIL - wrong type or values')
    failed += 1

print('\n' + SEP)
print('  Results: ' + str(passed) + ' passed, ' + str(failed) + ' failed')
print(SEP)
if failed:
    sys.exit(1)
