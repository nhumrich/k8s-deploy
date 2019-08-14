# k8s-deploy
Deployment for kubernetes


This is a docker container for deploying to kubernetes. It uses jinja templating for your kubernetes yaml file.

# To deploy

Drop a file `k8s-deployment.yaml` into the container (most CI's drop your repo into the container for you)
(or you can use another named file with the -f argument).

Run the command `python /scripts/k8s-deploy.py` to do the deploy.

You also need to provide a valid kube config with credentials. You can either drop that into the container at `/root/.kube/config`, or
provide it via the KUBECTL_CONFIG environment variable

# Variables

You can use jinja2 for templating. For example, if you provide the following string `{{ tag }}` anywhere in your yaml,
then you can pass in the tag via the command line, i.e. `python /scripts/k8s-deploy.py --tag v2.3` and it will replace that with `v2.3`.


# What does this give me?

This container provides two things. 1) The templating (for specifying tag/etc), but also a smart deployment for deployment object.
This script will run `kubectl apply` on your yaml file. So you can have many k8s objects in the yaml. If one or more of your objects is a "deployment",
then this script will run the deployment with auto-rollback. 
Here is how it works:

1) kubectl apply
2) pause the deployment (this will cause only one new pod to go up)
3) check status of the pod
4) If pod is bad, rollback, print logs
5) Otherwise, continue


In other words, you get auto-rollback on failure, and it prints the logs of the bad pod (if they exist).


See `example-k8s-deploy.yaml` for a basic deployment file.