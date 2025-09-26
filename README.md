### 프로젝트 실행 가이드
1. 공통 사항

프로젝트 구조
프로젝트 루트/
├─ backend/          # Python 백엔드
├─ frontend/         # React 프론트엔드
└─ .env              # 환경 변수
.env 파일은 백엔드, 프론트엔드 각각 필요한 값을 설정해야 합니다.
백엔드는 Python 3.11, 프론트엔드는 Node.js + npm/yarn 사용.

2. 윈도우 로컬 환경
2-1. 백엔드 실행
cd backend
python -m venv venv
.\venv\Scripts\activate

활성화되면 (venv) 표시가 터미널 앞에 붙음
pip install -r requirements.txt

## 백엔드 서버 실행
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload


2-2. 프론트엔드 실행


cd frontend
npm install
npm start
# 또는 yarn start


브라우저에서 http://localhost:3000
 으로 접속 가능

3. 리눅스 (EC2 아마존 리눅스) 환경
3-1. 백엔드 실행

백엔드 폴더 이동

cd backend


가상 환경 생성 및 활성화

python -m venv venv
source venv/bin/activate


의존성 설치

pip install -r requirements.txt


환경 변수 설정

nano .env


Windows와 동일하게 필요한 환경 변수 입력

백엔드 서버 실행

uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload


외부에서 접근 가능하도록 --host 0.0.0.0 설정

3-2. 프론트엔드 실행

프론트엔드 폴더 이동

cd ~/replanet_finished/replanet_v1313123/frontend


의존성 설치

npm install
# 또는 yarn install


환경 변수 설정

nano .env

REACT_APP_API_URL=http://EC2_공인_IP:8000


프론트엔드 서버 실행

npm start
# 또는 yarn start


EC2 공인 IP + 3000 포트로 외부 접속 가능: http://54.67.16.22:3000

54.67.16.22

4. 추가 팁

백엔드 재시작

ps aux | grep uvicorn    # 실행 중인 PID 확인
kill <PID>               # 프로세스 종료
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload


#### EC2에서 계속 실행

nohup uvicorn backend.main:app --host 0.0.0.0 --port 8000 & #제출시 백엔드
 
nohup serve -s build -l 3000 & #제출시 프론트엔드 

프론트: http://54.67.16.22:3000

백엔드: http://54.67.16.22:8000
로 접속가능

Git 동기화

git pull origin main


자동 동기화는 안 됨, 새 커밋 있을 때마다 pull 필요