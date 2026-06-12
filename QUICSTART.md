


```sh
# docker ps to get the container id
docker exec -it <container_id> python jobs/ingest/collect_ohlcv.py

# sans docker
source .venv/bin/activate
# python jobs/ingest/collect_ohlcv.py
python jobs/ingest/collect_ohlcv.py --symbol BTCUSDT --interval 1h
```

```sh
# Model Training
python models/src/train_model.py --epochs 1 --batch-size 32 --learning-rate 0.001






```sh
make dev-up
```