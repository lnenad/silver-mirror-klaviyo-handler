aws ecr get-login-password --region us-east-1 --profile silvermirror | docker login --username AWS --password-stdin 195509999935.dkr.ecr.us-east-1.amazonaws.com

docker build -t 195509999935.dkr.ecr.us-east-1.amazonaws.com/klaviyo_handler:latest .
docker tag klaviyo_handler:latest 195509999935.dkr.ecr.us-east-1.amazonaws.com/klaviyo_handler:latest
docker push 195509999935.dkr.ecr.us-east-1.amazonaws.com/klaviyo_handler:latest
