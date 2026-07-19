# ReVoice Deployment Guide

Deploy the ReVoice API to Alibaba Cloud Function Compute as a custom container.

## Prerequisites

- Alibaba Cloud account with Function Compute and Container Registry enabled
- Docker installed locally
- Serverless Devs CLI: `npm install -g @serverless-devs/s`
- Alibaba Cloud CLI configured: `aliyun configure`

---

## Step 1 — Configure credentials

```bash
# Run once to store your Alibaba Cloud credentials
aliyun configure

# Then configure Serverless Devs
s config add --AccessKeyID <your-key-id> --AccessKeySecret <your-key-secret> --alias default
```

---

## Step 2 — Build the frontend

```bash
cd apps/web
npm install
npm run build
cd ../..
# The dist/ folder is now at apps/web/dist/
```

---

## Step 3 — Build the Docker image

```bash
# Replace with your ACR namespace and region
REGISTRY=registry.ap-southeast-1.aliyuncs.com
NAMESPACE=your-namespace
IMAGE=${REGISTRY}/${NAMESPACE}/revoice:latest

docker build -t ${IMAGE} .
```

---

## Step 4 — Push to Alibaba Cloud Container Registry

```bash
# Log in to ACR
docker login registry.ap-southeast-1.aliyuncs.com

# Push the image
docker push ${IMAGE}
```

---

## Step 5 — Deploy to Function Compute

```bash
# Set the image URI in the env
export REGISTRY_IMAGE=${IMAGE}
export FC_REGION=ap-southeast-1

cd infra/alibaba
s deploy --use-local
```

After deployment, Serverless Devs prints the public HTTPS URL.

---

## Step 6 — Set real API keys (optional, post-deploy)

```bash
# Update the function's env vars with real keys
s cli fc3 function update \
  --region ap-southeast-1 \
  --functionName revoice-api \
  --environmentVariables '{"DASHSCOPE_API_KEY":"your_key","USE_MOCK_QWEN":"false","ALIBABA_ACCESS_KEY_ID":"...","OSS_BUCKET_NAME":"revoice-media"}'
```

---

## Local Docker test (before pushing)

```bash
docker run -p 8000:8000 \
  -e USE_MOCK_QWEN=true \
  -e DATABASE_URL=sqlite:///./revoice.db \
  ${IMAGE}

# Then open http://localhost:8000/health
```

---

## Alibaba Cloud services used

| Service | Purpose | Proof file |
|---|---|---|
| Function Compute (FC) | Serverless container hosting | `infra/alibaba/s.yaml` |
| Container Registry (ACR) | Docker image storage | step 4 above |
| OSS | Avatar image storage | `services/storage/oss_client.py` |

These three files are your **Proof of Alibaba Cloud Deployment** evidence for the hackathon submission.
