#include <stdlib.h>
#include <math.h>
typedef struct {double min,max,sum;int count;} Node;
typedef struct {int n;Node *nodes;} Tree;
static Node combine(Node a,Node b){Node r={fmin(a.min,b.min),fmax(a.max,b.max),a.sum+b.sum,a.count+b.count};return r;}
static void build(Tree*t,const double*v,int node,int left,int right){if(left==right){t->nodes[node]=(Node){v[left],v[left],v[left],1};return;}int mid=(left+right)/2;build(t,v,node*2,left,mid);build(t,v,node*2+1,mid+1,right);t->nodes[node]=combine(t->nodes[node*2],t->nodes[node*2+1]);}
void*tree_create(const double*values,int n){if(n<1)return NULL;for(int i=0;i<n;i++)if(!isfinite(values[i]))return NULL;Tree*t=malloc(sizeof(Tree));if(!t)return NULL;t->n=n;t->nodes=calloc(4*n,sizeof(Node));if(!t->nodes){free(t);return NULL;}build(t,values,1,0,n-1);return t;}
static Node query(Tree*t,int node,int left,int right,int start,int end,int*visited){(*visited)++;if(start<=left&&right<=end)return t->nodes[node];if(right<start||end<left)return(Node){INFINITY,-INFINITY,0,0};int mid=(left+right)/2;return combine(query(t,node*2,left,mid,start,end,visited),query(t,node*2+1,mid+1,right,start,end,visited));}
int tree_query(void*handle,int start,int end,double*out,int*visited){Tree*t=handle;if(!t||start<0||end>=t->n||start>end)return 0;*visited=0;Node r=query(t,1,0,t->n-1,start,end,visited);out[0]=r.min;out[1]=r.max;out[2]=r.sum;out[3]=r.count;return 1;}
void tree_free(void*handle){Tree*t=handle;if(t){free(t->nodes);free(t);}}
