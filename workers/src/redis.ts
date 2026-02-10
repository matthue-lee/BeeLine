import IORedis, { RedisOptions } from 'ioredis';
import { AppConfig } from './config';

export function createRedisOptions(config: AppConfig): RedisOptions {
  const url = new URL(config.redisUrl);
  const tlsOptions = config.redisTls ? { rejectUnauthorized: false } : undefined;
  return {
    host: url.hostname,
    port: Number(url.port || '6379'),
    password: url.password || undefined,
    username: url.username || undefined,
    tls: tlsOptions,
    keyPrefix: config.redisKeyPrefix + ':',
    lazyConnect: true
  };
}

export function createRedisConnection(config: AppConfig): IORedis {
  const opts = createRedisOptions(config);
  return new IORedis(opts);
}
