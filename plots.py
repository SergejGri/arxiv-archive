import os
import matplotlib.pyplot as plt
from taxonomy import CATEGORIES, TAXONOMY_MAP
from processing import get_count_by

os.makedirs("plots", exist_ok=True)



def plot_single_category(category: str) -> None:
    category = category.lower()
    sub_categories = list(TAXONOMY_MAP[category].keys())
    sub_categories_df = get_count_by(category=sub_categories)
    sorted_df = sub_categories_df.sort_values(by="count", ascending=False)

    plt.figure(figsize=(20, 6))
    plt.bar(sorted_df["sub_category"], sorted_df["count"])
    plt.xticks(rotation=90)
    plt.tight_layout()
    
    plt.savefig(f"plots/distribution_{category}.png")



plot_single_category(category="physics")