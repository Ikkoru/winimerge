import re, sys, collections
txt = open(sys.argv[1], errors='replace').read()
# split output into chunks ending with a CRASH block (sanitizer output precedes the CRASH line)
chunks = re.split(r'(CRASH seed \d+ it \d+ \(status -?\d+\); op log:\n(?:   .*\n)*)', txt)
res = collections.Counter(); examples = {}
for i in range(1, len(chunks), 2):
    san, crash = chunks[i-1], chunks[i]
    # last sanitizer report in san (after the last digest line)
    san = san.split('digest')[-1]
    frames = re.findall(r'#\d+ 0x[0-9a-f]+ in (\S+?)\(.*?\) \S*?/([A-Za-z]+\.hpp):(\d+)', san)
    frames += re.findall(r'#\d+ 0x[0-9a-f]+ in (\S+) \S*?/([A-Za-z]+\.hpp):(\d+)', san)
    top = next(((f, l) for (fn, f, l) in frames), None)
    fn = next((fn for (fn, f, l) in frames), '?')
    ops = [l.strip() for l in crash.splitlines()[1:]]
    last = ops[-1] if ops else '?'
    lastop = re.sub(r'\(.*', '', last)
    key = (fn.split('::')[-1], top, lastop)
    res[key] += 1
    if key not in examples:
        examples[key] = crash.splitlines()[0]
for k, v in res.most_common():
    print(v, k, examples[k])
