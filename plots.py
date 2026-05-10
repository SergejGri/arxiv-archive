import matplotlib.pyplot as plt

def plot():
    results = merge_categories()
    top_results = dict(list(results.items())[:50])

    plt.figure(figsize=(20, 6))
    plt.bar(top_results.keys(), top_results.values())
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    plt.savefig("plots/category_distribution.png")