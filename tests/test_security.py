import sys, os
sys.path.insert(0, os.path.abspath('.'))

from app.utils.security import hash_password, verify_password

SEP = '-' * 50
passed = 0
failed = 0

print(SEP)
print('  Security Layer Test - Password Hashing')
print(SEP)

# Test 1: hash is not the same as the plain password
print('\n[1] hash_password() does not return plain text')
hashed = hash_password('MySecurePassword123!')
if hashed != 'MySecurePassword123!':
    print('    PASS - hash differs from plain password')
    print('    hash prefix: ' + hashed[:10] + '...')
    passed += 1
else:
    print('    FAIL - hash equals plain password (CRITICAL)')
    failed += 1

# Test 2: hash starts with bcrypt identifier
print('\n[2] hash_password() produces a valid bcrypt hash')
if hashed.startswith('$2b$'):
    print('    PASS - starts with $2b$ (bcrypt identifier)')
    passed += 1
else:
    print('    FAIL - unexpected hash format: ' + hashed[:20])
    failed += 1

# Test 3: correct password verifies as True
print('\n[3] verify_password() returns True for correct password')
result = verify_password('MySecurePassword123!', hashed)
if result is True:
    print('    PASS - correct password verified')
    passed += 1
else:
    print('    FAIL - correct password was rejected')
    failed += 1

# Test 4: wrong password verifies as False
print('\n[4] verify_password() returns False for wrong password')
result = verify_password('WrongPassword!', hashed)
if result is False:
    print('    PASS - wrong password rejected')
    passed += 1
else:
    print('    FAIL - wrong password was accepted (CRITICAL)')
    failed += 1

# Test 5: empty string verifies as False (edge case)
print('\n[5] verify_password() returns False for empty string')
result = verify_password('', hashed)
if result is False:
    print('    PASS - empty password rejected')
    passed += 1
else:
    print('    FAIL - empty password was accepted (CRITICAL)')
    failed += 1

# Test 6: each call produces a different hash (salt is unique)
print('\n[6] Two calls to hash_password() produce different hashes')
hash1 = hash_password('SamePassword')
hash2 = hash_password('SamePassword')
if hash1 != hash2:
    print('    PASS - unique salt per hash confirmed')
    passed += 1
else:
    print('    FAIL - hashes are identical (no salt)')
    failed += 1

# Test 7: both hashes from test 6 still verify correctly
print('\n[7] Both salted hashes verify against the same plain password')
ok1 = verify_password('SamePassword', hash1)
ok2 = verify_password('SamePassword', hash2)
if ok1 and ok2:
    print('    PASS - both hashes verify correctly')
    passed += 1
else:
    print('    FAIL - one or both hashes failed verification')
    failed += 1

print('\n' + SEP)
print('  Results: ' + str(passed) + ' passed, ' + str(failed) + ' failed')
print(SEP)
if failed:
    sys.exit(1)
