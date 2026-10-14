"""Where the research folder is: the parent of this harness folder, or $RESEARCH_DIR."""
import os

ROOT = os.environ.get('RESEARCH_DIR') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, 'results')
TESTSET = os.path.join(ROOT, 'testset')
