# 🚇 seat-predictor

직장인·대학생을 위한 **"오늘 퇴근/하교길 버스·지하철 좌석 예측기"**

서울시 공공데이터를 기반으로 출발지 → 도착지 구간의 혼잡도와 시간대별 좌석 확률을 예측하고,
"몇 분 뒤에 타면 앉아서 갈 수 있는지" 알려주는 대시보드입니다.
현재는 **Streamlit + Mock Data**로 만든 프로토타입(MVP) 단계입니다.

## 🚀 실행 방법

### 1. 가상환경 생성 및 활성화

```bash
python3 -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 2. 라이브러리 설치

```bash
pip install -r requirements.txt
```

### 3. 앱 실행

```bash
streamlit run app.py
```

실행 후 브라우저에서 `http://localhost:8501` 로 접속하면 대시보드를 확인할 수 있습니다.

## 🛠 기술 스택

- [Streamlit](https://streamlit.io/) — 대시보드 UI
- [Pandas](https://pandas.pydata.org/) / [NumPy](https://numpy.org/) — 데이터 처리
- [Plotly](https://plotly.com/python/) — 시간대별 좌석 확률 시각화

## 📊 관련 데이터셋 링크 (서울시 열린데이터광장)

1. 지하철 시간대별 승하차 데이터
   - [서울시 지하철 호선별 역별 시간대별 승하차 인원 정보](https://data.seoul.go.kr/dataList/OA-12914/S/1/datasetView.do)
2. 버스 시간대별 승하차 데이터
   - [서울시 버스노선별 정류장별 시간대별 승하차 인원 정보](https://data.seoul.go.kr/dataList/OA-12912/S/1/datasetView.do)
3. 지하철 혼잡도 데이터 (추가 고려)
   - [서울교통공사 지하철 혼잡도 정보](https://data.seoul.go.kr/dataList/OA-21288/S/1/datasetView.do)
