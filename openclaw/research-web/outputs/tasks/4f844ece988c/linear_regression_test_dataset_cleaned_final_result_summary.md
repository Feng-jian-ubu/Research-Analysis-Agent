# 统计分析报告

**生成时间:** 2026-08-19 18:25:21

**方法:** 逻辑回归

**目标变量 (Y):** renovation_score
  
**自变量 (X):** house_id, area_sqm, age_years, distance_km, bedrooms, price_wan

---

## 样本信息

- 总样本量: 105
- 有效样本量: 99

## 检验结果

- **accuracy:** 0.9333
- **auc_roc:** 0.9866
- **n_features:** 6
- **p 值:** N/A

## 效应量

- **accuracy:** 0.9333
- **auc_roc:** 0.9866
- **强度:** 优秀

## 回归系数

| 变量 | 系数 |
|------|------|
| house_id | -0.0222 |
| area_sqm | -0.5495 |
| age_years | 0.3089 |
| distance_km | 1.3344 |
| price_wan | 0.4784 |
| bedrooms | -1.9617 |

## 结论

逻辑回归: 准确率=0.933, AUC=0.987


## 复现代码

```python
from sklearn.linear_model import LogisticRegression

X = df[['house_id', 'area_sqm', 'age_years', 'distance_km', 'bedrooms', 'price_wan']]
X = pd.get_dummies(X, columns=['bedrooms'], drop_first=True)
y = df['renovation_score']
model = LogisticRegression(max_iter=1000).fit(X, y)
print(f'Accuracy = {model.score(X, y):.3f}')
```
