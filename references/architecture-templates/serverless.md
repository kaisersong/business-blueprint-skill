# AWS Serverless Architecture Template

## 适用场景

用户描述包含：Lambda、API Gateway、DynamoDB、Serverless、无服务器等关键词。

## 布局结构

```
Clients → CloudFront → API Gateway → Lambda → DynamoDB
                                    → SQS
                                    → S3
```

## 组件定义

| 组件 | 类别 | x | y | 宽 | 高 | 特征 |
|------|------|---|---|-----|-----|------|
| Clients | external | 80 | 230 | 140 | 80 | Web/Mobile |
| CloudFront | cloud | 310 | 230 | 140 | 80 | CDN |
| API Gateway | cloud | 500 | 230 | 160 | 80 | REST API, WebSocket, HTTPS |
| Lambda | backend | 720 | 230 | 150 | 80 | Functions, Auto-scaling |
| SQS | message_bus | 720 | 130 | 150 | 44 | Message Queue |
| S3 | cloud | 720 | 360 | 150 | 80 | Object Storage |
| DynamoDB | database | 930 | 230 | 160 | 80 | NoSQL, On-demand |

## 连接关系

| 从 | 到 | 方向 |
|----|----|------|
| Clients | CloudFront | 水平 → |
| CloudFront | API Gateway | 水平 → |
| API Gateway | Lambda | 水平 → |
| Lambda | SQS | 垂直 ↑ |
| Lambda | S3 | 垂直 ↓ |
| Lambda | DynamoDB | 水平 → |

## AWS Region

- 虚线框：x=260, y=110, width=900, height=350, rx=16
- 描边：`#F59E0B`, `stroke-dasharray="8,4"`, `opacity="0.4"`
- 标签：`AWS Region: us-east-1`（x=280, y=100）
- Clients 在 Region 框外左侧

## Summary Cards

### Infrastructure (琥珀色)
- CloudFront CDN distribution
- API Gateway REST endpoints
- S3 static asset hosting
- SQS message queues

### Compute (翠绿色)
- Lambda functions
- Auto-scaling to zero
- Pay-per-invocation
- 15 min max execution

### Data (紫色)
- DynamoDB tables
- On-demand capacity
- Global secondary indexes
- Point-in-time recovery
