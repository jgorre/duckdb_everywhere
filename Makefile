## Postgres DB ##

###

## Python App ## 

build-python-app:
	docker build -t pancake-backend:latest ./python_pancake_app

apply-python-app:
	kubectl apply -f ./python_pancake_app/kube/01-deployment.yaml
	kubectl apply -f ./python_pancake_app/kube/02-service.yaml
	kubectl rollout restart deployment pancake-backend

python-app:
	make build-python-app
	make apply-python-app


### DuckDB Extract

lakekeeper-port-forward:
	kubectl port-forward svc/my-lakekeeper 8181:8181

copy_extract_venv_path:
	echo "./2_duckdb_extract/extract_venv/bin/activate" | pbcopy && echo "Extract venv path copied to clipboard."

run_extract:
	python3 ./2_duckdb_extract/extract.py

build_extract_image:
	docker build -t duckdb-extract:latest ./2_duckdb_extract

apply_extract_kube:
	make build_extract_image
	kubectl delete job pancake-extract --ignore-not-found=true
	kubectl apply -f ./2_duckdb_extract/kube/01-job.yaml

run_minio_bucket_init:
	kubectl create configmap minio-init-script \
		--from-file=init.sh=./3_iceberg/kube/minio/init.sh \
		--from-file=buckets=./3_iceberg/kube/minio/buckets \
		--dry-run=client -o yaml | kubectl apply -f -
	kubectl delete job minio-init --ignore-not-found=true
	kubectl apply -f ./3_iceberg/kube/minio/05-minio-init-job.yaml
