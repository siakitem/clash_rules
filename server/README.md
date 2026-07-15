# Subconverter profile service

该目录来自云端实际运行的 `chain-dialer` 服务，并重构为一份公共规则模板加两个确定性 profile。

## Profiles

- `company`：局域网规则保持 `DIRECT`；其余策略组中的 `DIRECT` 全部替换为公司 SOCKS5；所有上游代理节点通过 `dialer-proxy` 使用公司 SOCKS5。
- `home`：不生成公司 SOCKS5，也不允许上游节点保留 `dialer-proxy`；常规公网组只使用 `DIRECT`。

订阅接口：

```text
/<service-token>/sub/<source>/<source-token>/clash/company
/<service-token>/sub/<source>/<source-token>/clash/home
```

旧的 `/clash` 接口由 `LEGACY_PROFILE` 控制，迁移期间默认保持 `company` 行为。

## Configuration

1. 复制 `configuration.sample` 为不会提交的 `environment`，填入真实 token 和公司 SOCKS5 参数。
2. 复制 `sources.sample.yaml` 为不会提交的 `sources.yaml`，填入节点源 URL 和独立 token。
3. 把 `SUBCONVERTER_IMAGE` 固定到明确 tag 或 digest，并把 `COMMON_CONFIG_URL` 固定到已经验证的 Git commit，不能使用浮动的 `latest` 和 `master`。
4. 启动服务：`docker compose up -d --build`。

Nginx 需要同时放行旧 `/clash` 和新的 `/clash/company`、`/clash/home` 路径，可从 `nginx.sample.conf` 复制 location。订阅 URL 包含 bearer token，响应不得标记成 `public` 共享缓存。

服务会把节点 URL 和公共模板 URL同时交给 subconverter，一次生成完整中性配置；Python 层只做 profile 转换和严格校验，不再重复下载节点订阅和模板。

## Safety invariants

公司配置生成失败而不是降级直连，条件包括：

- 公网规则仍然指向原生 `DIRECT`；
- 任一上游节点未设置公司 SOCKS5 为 `dialer-proxy`；
- 任一公网策略组仍可到达 `DIRECT`、`PASS` 或 `COMPATIBLE`；
- 公司 SOCKS5 不在局域网地址范围；
- 策略组存在循环或未知引用。

这些校验只约束 Mihomo 配置。要实现核心退出时也不泄漏公网流量，还需要在公司路由器上增加防直连 firewall 规则，并单独处理 DNS、订阅更新和 NTP 等路由器自身流量。
