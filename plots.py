import os
import matplotlib.pyplot as plt
from taxonomy import TAXONOMY_MAP, humanize_categories
from processing import *

os.makedirs("plots", exist_ok=True)



def plot_single_category(category: str) -> None:
    category = category.lower()
    sub_categories = list(TAXONOMY_MAP[category].keys())
    sub_categories_df = get_count_by(category=sub_categories)
    sorted_df = sub_categories_df.sort_values(by="count", ascending=False)
    #sorted_df = humanize_id(sorted_df, category)
    
    plt.figure(figsize=(20, 6))
    plt.bar(sorted_df["sub_category"], sorted_df["count"])
    plt.xticks(rotation=90)
    plt.tight_layout()
    
    plt.savefig(f"plots/distribution_{category}.png")



plot_single_category(category="physics")