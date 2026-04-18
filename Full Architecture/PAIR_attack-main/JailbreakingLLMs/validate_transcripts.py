import json, glob

files = sorted(glob.glob('transcripts/*.json'))
print(f'Total transcripts: {len(files)}')
print()
header = f"{'Attacker':<28} {'Target':<28} {'Goal':<35} {'Success':<10} {'Queries'}"
print(header)
print('-' * len(header))
for f in files:
    d = json.load(open(f, encoding='utf-8'))
    attacker = d['attacker_model']
    target = d['target_model']
    goal = d['goal'][:33] + '..' if len(d['goal']) > 33 else d['goal']
    success = 'YES' if d['success'] else 'NO'
    queries = str(d['queries_to_jailbreak']) if d['queries_to_jailbreak'] else '-'
    print(f"{attacker:<28} {target:<28} {goal:<35} {success:<10} {queries}")
