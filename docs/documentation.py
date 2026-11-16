"""Check client document coverage, local links and portable Skill metadata."""
import argparse,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def documents(root):
 result=subprocess.run(['git','-C',str(root),'ls-files','-co','--exclude-standard','--','*.md'],capture_output=True,text=True)
 return sorted(set(result.stdout.splitlines())) if result.returncode==0 else sorted(str(p.relative_to(root)) for p in root.rglob('*.md'))
def inventory(root=ROOT):
 return {'schema':'loom-use-documentation/v1','documents':[{'path':p,'audience':'agent' if p.endswith('SKILL.md') or p=='AGENTS.md' else 'maintainer' if p.startswith('clients/') or p=='docs/verification.md' else 'reader','authority':'client setup and refresh; server behavior via live discovery','status':'legal' if p=='THIRD_PARTY_NOTICES.md' else 'current'} for p in documents(root)]}
def check(root=ROOT):
 errors=[];catalog=root/'docs/documentation-catalog.json'
 if not catalog.exists() or json.loads(catalog.read_text())!=inventory(root):errors.append('Documentation inventory is missing/stale')
 for path in documents(root):
  text=(root/path).read_text();prose=re.sub(r'(?ms)^(```|~~~).*?^\1[^\n]*\n?', '',text)
  for target in re.findall(r'\]\(([^\s)]+)\)',prose):
   if ':' in target or target.startswith(('/', '#')) or '<' in target:continue
   if not (root/path).parent.joinpath(target.partition('#')[0]).exists():errors.append(path+': missing link '+target)
  if path.endswith('SKILL.md'):
   match=re.match(r'---\n(.*?)\n---\n',text,re.S)
   if not match:errors.append(path+': missing Skill frontmatter');continue
   fields=dict(re.findall(r'^([a-z-]+): (.+)$',match[1],re.M));name=fields.get('name','');description=fields.get('description','')
   if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',name) or len(name)>64 or Path(path).parent.name!=name:errors.append(path+': invalid Skill name')
   if not description or len(description)>1024:errors.append(path+': invalid Skill description')
 return errors
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['build','check']);a=p.parse_args()
 if a.operation=='build':(ROOT/'docs/documentation-catalog.json').write_text(json.dumps(inventory(),indent=2)+'\n')
 errors=check();print('\n'.join(errors) if errors else f'{len(documents(ROOT))} documents checked');raise SystemExit(bool(errors))
