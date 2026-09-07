# 阶段 02 来源定位抽查

- 旧 RWE JSON：记录定位形如 `$.xx_v1[0]`，值定位形如 `$.xx_v1[0].total`；数组索引从 0 开始。
- CSV 长表：记录定位形如 `row:2`，值定位形如 `row:2:col:value`；行号为原始文件物理行号，表头为第 1 行。
- Excel 宽表：记录定位形如 `sheet:XX-v1:row:2`，值定位形如 `sheet:XX-v1:row:2:col:total`。
- 嵌套 JSON：记录定位形如 `$.subjects[0].records[0]`，值定位形如 `$.subjects[0].records[0].total`。

本阶段只追溯到导出文件或输入文件本身；如果原始数据库记录号没有出现在导出文件中，不补造数据库级 provenance。
