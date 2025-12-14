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