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
