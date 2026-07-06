"""seat-predictor 백엔드 (FastAPI).

core/ 의 예측·데이터 로직을 REST API로 노출하는 얇은 서버 계층이다. 화면 코드
(app.py, mobile_demo.py)와 동일한 core 로직을 공유하므로, 앞으로 만들 모바일
웹앱(PWA)이나 다른 클라이언트가 같은 API를 사용할 수 있다.
"""
