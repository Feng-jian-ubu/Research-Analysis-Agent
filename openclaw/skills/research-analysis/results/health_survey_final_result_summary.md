# 统计分析报告

**生成时间:** 2026-08-18 22:58:41

**方法:** 线性回归

**目标变量 (Y):** health_score
  
**自变量 (X):** age, height, weight, exercise_hours, sleep_hours, income, education, region, occupation, married, smoker

---

## 样本信息

- 总样本量: 120000
- 有效样本量: 112935

## 假设前提检查

- ✅ **正态性 (Shapiro-Wilk)**: p=0.5000 — n>5000, 建议看Q-Q图

## 检验结果

- **R_squared:** 0.7445
- **adjusted_R_squared:** 0.7444
- **F_statistic:** 10964.7654
- **F_p_value:** 0.0000
- **df_model:** 30
- **df_residual:** 112904
- **p 值:** 0.000000

## 效应量

- **R_squared:** 0.7445
- **adjusted_R_squared:** 0.7444
- **强度:** 强

## 回归系数

| 变量 | 系数 |
|------|------|
| height | 0.0001 |
| weight | -0.2986 |
| exercise_hours | 1.4852 |
| sleep_hours | 1.1995 |
| income | -0.0 |
| age | 0.2012 |
| married | 3.0141 |
| smoker | -5.0532 |
| education_大专 | -11.0359 |
| education_本科 | -8.0544 |
| education_硕士 | -3.0044 |
| education_高中 | -16.08 |
| region_北京 | -0.0558 |
| region_南京 | 5.028 |
| region_天津 | 5.0156 |
| region_广州 | 4.9755 |
| region_成都 | 6.93 |
| region_杭州 | 6.9935 |
| region_武汉 | 4.9533 |
| region_深圳 | -0.0736 |
| region_苏州 | 4.9845 |
| region_西安 | 5.0034 |
| region_重庆 | 4.976 |
| occupation_医生 | -0.1572 |
| occupation_学生 | -0.0289 |
| occupation_工程师 | -0.0672 |
| occupation_教师 | -0.0666 |
| occupation_自由职业 | -0.0644 |
| occupation_退休 | -0.0397 |
| occupation_销售 | -0.0152 |

## 结论

线性回归: 11 个变量对 health_score 的回归模型显著 (R²=0.7445, adj.R²=0.7444, F=10964.765, p=0.0000)


## 复现代码

```python
from sklearn.linear_model import LinearRegression

X = df[['age', 'height', 'weight', 'exercise_hours', 'sleep_hours', 'income', 'education', 'region', 'occupation', 'married', 'smoker']]
X = pd.get_dummies(X, columns=['age', 'education', 'region', 'occupation', 'married', 'smoker'], drop_first=True)
y = df['health_score']
model = LinearRegression().fit(X, y)
print(f'R² = {model.score(X, y):.4f}')
```
