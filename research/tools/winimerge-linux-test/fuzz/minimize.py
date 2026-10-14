import subprocess, os, sys
binary, seed, it = sys.argv[1], sys.argv[2], sys.argv[3]
env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='print_stacktrace=0')
def crashes(skip):
    e = dict(env, SKIP=','.join(map(str, sorted(skip))))
    r = subprocess.run([binary, '1', seed, it], env=e, capture_output=True, text=True, timeout=120)
    return 'CRASH' in r.stdout, r.stdout
skip = set()
assert crashes(skip)[0]
for step in range(40):
    if crashes(skip | {step})[0]:
        skip.add(step)
ok, out = crashes(skip)
print('kept steps:', sorted(set(range(40)) - skip))
print(out)
