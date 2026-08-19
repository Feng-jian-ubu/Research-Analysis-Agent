# 数据分析报告

> 生成时间：2026-08-19 18:25:25

---

<!-- meta: {
  "generated_at": "2026-08-19 18:25:25",
  "tool": "reportgenerator.py",
  "skill": "research-analysis",
  "n_analyses": 1,
  "methods": [
    "逻辑回归"
  ],
  "data": {
    "n_rows": 105,
    "n_cols": 7,
    "numeric_vars": 7,
    "categorical_vars": 0,
    "missing_total": 6
  },
  "analysis_0": {
    "method": "逻辑回归",
    "y": "renovation_score",
    "x": [
      "house_id",
      "area_sqm",
      "age_years",
      "distance_km",
      "bedrooms",
      "price_wan"
    ],
    "p_value": null,
    "sample_size": {
      "total": 105,
      "valid": 99
    }
  }
} -->

## 摘要

逻辑回归：逻辑回归: 准确率=0.933, AUC=0.987

---

## 1. 数据与方法

### 1.1 数据概览

- **样本量**：105 条观测
- **变量数**：7 个变量 （7 个数值型，0 个分类型）
- **缺失值**：共 6 个

### 1.2 分析方法

**分析 1：逻辑回归**

- 方法说明：逻辑回归，用于分析自变量对二分类因变量的预测作用
- **目标变量 (Y)**：renovation_score
- **自变量 (X)**：house_id、area_sqm、age_years、distance_km、bedrooms、price_wan
- **样本量**：99/105 有效

---

## 2. 统计结果

### 2.1 逻辑回归

采用逻辑回归模型预测 renovation_score。模型在测试集上的准确率为 0.933。AUC-ROC = 0.987。AUC = 0.987，模型区分能力优秀。 模型系数：house_id (OR=0.9781；area_sqm (OR=0.5772；age_years (OR=1.3619；distance_km (OR=3.7977；price_wan (OR=1.6135；bedrooms (OR=0.1406。

**检验统计量：**

- **accuracy**：0.9333
- **auc_roc**：0.9866
- **n_features**：6

**效应量：**

- **accuracy**：0.9333
- **auc_roc**：0.9866
- **强度评价**：优秀

---

## 3. 讨论

### 3.1 对分析 1 的讨论

效应量分析表明AUC = 0.987，模型区分能力优秀。

样本量较充足 (n=105)，结论具有较好的统计效力。

### 局限性

本报告的分析结果受限于以下因素：

- 数据质量：分析结果依赖于原始数据的准确性和完整性。
- 样本代表性：样本需能够代表其所属总体。
- 模型假设：统计方法的结论有效性取决于其前提假设的满足程度。

---

## 4. 结论

逻辑回归：逻辑回归: 准确率=0.933, AUC=0.987

---

## 附录：统计数值明细

> 以下为各分析的完整统计量数值，供查验与复现。

### A.1 逻辑回归

```json
{
  "method": "逻辑回归",
  "y_col": "renovation_score",
  "x_vars": [
    "house_id",
    "area_sqm",
    "age_years",
    "distance_km",
    "bedrooms",
    "price_wan"
  ],
  "sample_size": {
    "total": 105,
    "valid": 99
  },
  "statistics": {
    "accuracy": 0.9333,
    "auc_roc": 0.9866,
    "n_features": 6,
    "coefficients": [
      {
        "feature": "house_id",
        "coef": -0.0222,
        "odds_ratio": 0.9781
      },
      {
        "feature": "area_sqm",
        "coef": -0.5495,
        "odds_ratio": 0.5772
      },
      {
        "feature": "age_years",
        "coef": 0.3089,
        "odds_ratio": 1.3619
      },
      {
        "feature": "distance_km",
        "coef": 1.3344,
        "odds_ratio": 3.7977
      },
      {
        "feature": "price_wan",
        "coef": 0.4784,
        "odds_ratio": 1.6135
      },
      {
        "feature": "bedrooms",
        "coef": -1.9617,
        "odds_ratio": 0.1406
      }
    ]
  },
  "p_value": null,
  "effect_size": {
    "accuracy": 0.9333,
    "auc_roc": 0.9866,
    "interpretation": "优秀"
  },
  "ci_95": {},
  "interpretation": "逻辑回归: 准确率=0.933, AUC=0.987",
  "code_snippet": "from sklearn.linear_model import LogisticRegression\n\nX = df[['house_id', 'area_sqm', 'age_years', 'distance_km', 'bedrooms', 'price_wan']]\nX = pd.get_dummies(X, columns=['bedrooms'], drop_first=True)\ny = df['renovation_score']\nmodel = LogisticRegression(max_iter=1000).fit(X, y)\nprint(f'Accuracy = {model.score(X, y):.3f}')"
}
```
