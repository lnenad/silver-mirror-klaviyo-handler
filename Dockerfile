FROM public.ecr.aws/lambda/python:3.10
# Copy the earlier created requirements.txt file to the container

COPY . ${LAMBDA_TASK_ROOT}
COPY requirements.txt  .
RUN  pip3 install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Set the CMD to your handler
CMD ["app.lambda_handler"]
