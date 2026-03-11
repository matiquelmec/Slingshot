import subprocess

with open('audit_results.txt', 'w', encoding='utf-8') as f:
    f.write('=== GIT STATUS ===\n')
    status = subprocess.run(['git', 'status', '-s'], capture_output=True, text=True, encoding='utf-8')
    f.write(status.stdout)
    f.write('\n=== GIT LOG ===\n')
    log = subprocess.run(['git', 'log', '-n', '5', '--oneline'], capture_output=True, text=True, encoding='utf-8')
    f.write(log.stdout)
