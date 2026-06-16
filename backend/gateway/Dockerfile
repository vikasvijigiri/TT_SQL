FROM golang:1.24-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go build -o server ./cmd/server/

FROM alpine:3.21
RUN apk add --no-cache wget
WORKDIR /app
COPY --from=builder /app/server .
EXPOSE 8002
HEALTHCHECK --interval=20s --timeout=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8002/api/health || exit 1
CMD ["./server"]
