# Microservices Architecture Template

## 适用场景

用户描述包含：微服务、microservices、service mesh、Kubernetes、K8s、分布式服务等关键词。

## 布局结构

```
Clients → API Gateway → [Service A, Service B, Service C] → [DB A, DB B, Cache, MQ]
```

## 组件定义

| 组件 | 类别 | x | y | 宽 | 高 | 特征 |
|------|------|---|---|-----|-----|------|
| Clients | external | 80 | 280 | 140 | 80 | Web/Mobile |
| API Gateway | cloud | 310 | 280 | 150 | 80 | Routing, Auth |
| Service A | backend | 540 | 160 | 150 | 80 | 业务服务 |
| Service B | backend | 540 | 280 | 150 | 80 | 用户服务 |
| Service C | backend | 540 | 400 | 150 | 80 | 订单服务 |
| DB A | database | 780 | 160 | 140 | 80 | 业务数据 |
| DB B | database | 780 | 280 | 140 | 80 | 用户数据 |
| Cache | database | 780 | 400 | 140 | 44 | Redis/ElastiCache |
| MQ | message_bus | 780 | 500 | 140 | 44 | RabbitMQ/Kafka |

## 连接关系

| 从 | 到 | 方向 |
|----|----|------|
| Clients | API Gateway | 水平 → |
| API Gateway | Service A | 水平 → |
| API Gateway | Service B | 水平 → |
| API Gateway | Service C | 水平 → |
| Service A | DB A | 水平 → |
| Service B | DB B | 水平 → |
| Service C | Cache | 水平 → |
| Service C | MQ | 水平 → |

## K8s Cluster Region

- 虚线框：x=290, y=120, width=660, height=450, rx=16
- 描边：`#FBBF24`, `stroke-dasharray="8,4"`, `opacity="0.4"`
- 标签：`Kubernetes Cluster`（x=310, y=110）
- Clients 在 Cluster 框外左侧

## Summary Cards

### Gateway (琥珀色)
- API Gateway routing
- Authentication & authorization
- Rate limiting
- Load balancing

### Services (翠绿色)
- Microservice A/B/C
- Independent deployment
- Service discovery
- Health monitoring

### Data (紫色)
- Database per service
- Redis caching layer
- Message queue
- Event-driven communication
