# 루트에 conftest.py가 있어야 pytest가 프로젝트 루트를 sys.path에 넣어주고,
# tests/에서 clawler·entity·repository·service를 패키지 설치 없이 import할 수 있다.
# (내용은 비어 있어도 되지만 파일 자체는 지우면 안 된다)
